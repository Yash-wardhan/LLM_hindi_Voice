"""
Voice Chat Router
─────────────────
POST /api/v1/voice/chat       — Audio upload → STT → LLM → TTS pipeline
POST /api/v1/voice/text-chat  — Text input  → LLM → TTS  (no audio upload)
"""

import base64
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.models.schemas import TextChatRequest, TextChatResponse, VoiceChatResponse
from app.services import llm_service, stt_service, tts_service
from app.services.memory_service import memory_service

router = APIRouter()

_MAX_BYTES = settings.AUDIO_MAX_SIZE_MB * 1024 * 1024


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_session(session_id: Optional[str]) -> str:
    """Return existing session_id or generate a new UUID."""
    return session_id if session_id else str(uuid.uuid4())


def _validate_audio(file: UploadFile) -> None:
    content_type = (file.content_type or "").lower()
    if content_type not in settings.AUDIO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported audio type '{content_type}'. "
                f"Allowed: {', '.join(settings.AUDIO_ALLOWED_TYPES)}"
            ),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=VoiceChatResponse,
    summary="Voice Chat — Audio In / Audio Out",
    description=(
        "Upload an audio file. The API will:\n"
        "1. Transcribe speech → text (Whisper)\n"
        "2. Detect Hindi intent (slang-aware GPT)\n"
        "3. Generate an AI reply\n"
        "4. Convert reply text → speech (TTS)\n"
        "5. Return transcript, intent, reply text, and base64 audio."
    ),
)
async def voice_chat(
    audio: Annotated[UploadFile, File(description="Audio file (wav/mp3/webm/ogg/m4a/flac)")],
    session_id: Annotated[
        Optional[str],
        Form(description="Session ID for conversation continuity. Leave blank to start new."),
    ] = None,
) -> VoiceChatResponse:
    # ── 1. Validate file type ──────────────────────────────
    _validate_audio(audio)

    # ── 2. Read audio bytes (enforce size limit) ───────────
    audio_bytes = await audio.read(_MAX_BYTES + 1)
    if len(audio_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds the {settings.AUDIO_MAX_SIZE_MB} MB limit.",
        )

    # ── 3. Speech → Text ───────────────────────────────────
    try:
        transcript = await stt_service.transcribe_audio(
            audio_bytes,
            content_type=audio.content_type or "audio/webm",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"STT service error: {exc}",
        )

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not transcribe audio — audio may be silent or unclear.",
        )

    # ── 4. Resolve session & fetch memory ──────────────────
    sid = _resolve_session(session_id)
    history = memory_service.get_history(sid)

    # ── 5. LLM — intent detection + AI reply ───────────────
    try:
        llm_result = await llm_service.get_ai_reply(history, transcript)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )

    # ── 6. Save exchange to memory ─────────────────────────
    memory_service.add_exchange(sid, transcript, llm_result.reply)

    # ── 7. TTS — reply text → speech ───────────────────────
    try:
        audio_out = await tts_service.synthesize_speech(llm_result.reply)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS service error: {exc}",
        )

    audio_b64 = base64.b64encode(audio_out).decode("utf-8")

    # ── 8. Return full response ────────────────────────────
    return VoiceChatResponse(
        session_id=sid,
        transcript=transcript,
        intent=llm_result.intent,
        language_detected=llm_result.language,
        reply_text=llm_result.reply,
        reply_audio_b64=audio_b64,
        reply_audio_format=settings.TTS_FORMAT,
    )


@router.post(
    "/text-chat",
    response_model=TextChatResponse,
    summary="Text Chat — Text In / Text + Audio Out",
    description="Send a text message. Returns AI reply text and optionally a TTS audio (base64).",
)
async def text_chat(body: TextChatRequest) -> TextChatResponse:
    sid = _resolve_session(body.session_id)
    history = memory_service.get_history(sid)

    # ── LLM ───────────────────────────────────────────────
    try:
        llm_result = await llm_service.get_ai_reply(history, body.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )

    memory_service.add_exchange(sid, body.message, llm_result.reply)

    # ── Optional TTS ──────────────────────────────────────
    audio_b64: Optional[str] = None
    if body.tts:
        try:
            audio_out = await tts_service.synthesize_speech(llm_result.reply)
            audio_b64 = base64.b64encode(audio_out).decode("utf-8")
        except Exception as exc:
            # TTS failure is non-fatal for text-chat
            audio_b64 = None

    return TextChatResponse(
        session_id=sid,
        intent=llm_result.intent,
        language_detected=llm_result.language,
        reply_text=llm_result.reply,
        reply_audio_b64=audio_b64,
        reply_audio_format=settings.TTS_FORMAT if audio_b64 else None,
    )
