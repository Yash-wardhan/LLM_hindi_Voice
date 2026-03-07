"""
Voice Chat Router
─────────────────
POST /api/v1/voice/chat       — Audio upload → STT → LLM → TTS pipeline
POST /api/v1/voice/stream     — Audio upload → STT → LLM → TTS bytes streamed
POST /api/v1/voice/text-chat  — Text input  → LLM → TTS  (no audio upload)
WS   /api/v1/voice/ws         — Real-time bidirectional WebSocket pipeline
                                  client sends audio chunks → server streams
                                  transcript + reply text + TTS audio back
"""

import base64
import json
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

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
        emotion=llm_result.emotion,
        reply_text=llm_result.reply,
        reply_audio_b64=audio_b64,
        reply_audio_format=settings.TTS_FORMAT,
    )


# ── TTS format → MIME type map ───────────────────────────────────────────────
_AUDIO_MIME = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
}


@router.post(
    "/stream",
    summary="Voice Stream — Audio In / Audio Bytes Streamed Out",
    description=(
        "Upload an audio file. The API will:\n"
        "1. Transcribe speech → text (Whisper)\n"
        "2. Detect Hindi intent (slang-aware GPT)\n"
        "3. Generate an AI reply\n"
        "4. Stream reply audio back in real-time chunks (no base64)\n"
        "\n"
        "Metadata (transcript, intent, language, emotion, reply text) is returned "
        "as response headers (`X-Transcript`, `X-Intent`, `X-Language`, "
        "`X-Emotion`, `X-Reply-Text`, `X-Session-Id`)."
    ),
    response_class=StreamingResponse,
)
async def voice_stream(
    audio: Annotated[UploadFile, File(description="Audio file (wav/mp3/webm/ogg/m4a/flac)")],
    session_id: Annotated[
        Optional[str],
        Form(description="Session ID for conversation continuity. Leave blank to start new."),
    ] = None,
) -> StreamingResponse:
    # ── 1. Validate & read audio ───────────────────────────────
    _validate_audio(audio)
    audio_bytes = await audio.read(_MAX_BYTES + 1)
    if len(audio_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds the {settings.AUDIO_MAX_SIZE_MB} MB limit.",
        )

    # ── 2. Speech → Text ──────────────────────────────────────
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

    # ── 3. LLM reply ────────────────────────────────────────────
    sid = _resolve_session(session_id)
    history = memory_service.get_history(sid)

    try:
        llm_result = await llm_service.get_ai_reply(history, transcript)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )

    memory_service.add_exchange(sid, transcript, llm_result.reply)

    # ── 4. Stream TTS audio ────────────────────────────────────
    media_type = _AUDIO_MIME.get(settings.TTS_FORMAT, "audio/mpeg")

    return StreamingResponse(
        tts_service.stream_speech(llm_result.reply),
        media_type=media_type,
        headers={
            "X-Session-Id": sid,
            "X-Transcript": transcript,
            "X-Intent": llm_result.intent,
            "X-Language": llm_result.language,
            "X-Emotion": llm_result.emotion,
            "X-Reply-Text": llm_result.reply,
        },
    )


# ── WebSocket Real-Time Voice Pipeline ────────────────────────────────────────
#
# Protocol (one turn = one user utterance):
#
#   CLIENT → SERVER  binary frames  : raw audio chunks from microphone
#   CLIENT → SERVER  text frame     : {"type":"end_of_speech","content_type":"audio/webm"}
#                                      signals that all audio for this turn is sent
#   SERVER → CLIENT  text frame     : {"type":"transcript","text":"..."}
#   SERVER → CLIENT  text frame     : {"type":"reply_text","text":"...",
#                                       "intent":"...","language":"...","emotion":"..."}
#   SERVER → CLIENT  binary frames  : TTS audio chunks streamed progressively
#   SERVER → CLIENT  text frame     : {"type":"done"}
#                                      turn is complete; ready for next utterance
#
# The connection stays open for multi-turn conversation.
# Close the WebSocket from the client side to end the session.
#
# On any pipeline error the server sends:
#   SERVER → CLIENT  text frame     : {"type":"error","detail":"..."}
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def voice_websocket(
    websocket: WebSocket,
    session_id: Optional[str] = None,
) -> None:
    """
    Real-time bidirectional voice pipeline over WebSocket.

    Query params:
        session_id  (optional) — resume an existing conversation session.
                                  Omit to start a fresh session.
    """
    await websocket.accept()

    sid = _resolve_session(session_id)

    # Announce connection + assigned session
    await websocket.send_text(json.dumps({"type": "ready", "session_id": sid}))

    audio_buffer: list[bytes] = []
    content_type: str = "audio/webm"

    try:
        while True:
            # ── Receive next frame ─────────────────────────────────────
            message = await websocket.receive()

            # ── Disconnect frame → exit cleanly ────────────────────────
            if message.get("type") == "websocket.disconnect":
                break

            # ── Binary frame → accumulate audio ───────────────────────
            if "bytes" in message and message["bytes"] is not None:
                audio_buffer.append(message["bytes"])
                continue

            # ── Text frame → parse control message ────────────────────
            if "text" in message and message["text"] is not None:
                try:
                    ctrl = json.loads(message["text"])
                except json.JSONDecodeError:
                    await websocket.send_text(
                        json.dumps({"type": "error", "detail": "Invalid JSON control message."})
                    )
                    continue

                msg_type = ctrl.get("type", "")

                # Client signals end of its audio for this turn
                if msg_type == "end_of_speech":
                    content_type = ctrl.get("content_type", "audio/webm")

                    if not audio_buffer:
                        await websocket.send_text(
                            json.dumps({"type": "error", "detail": "No audio received before end_of_speech."})
                        )
                        continue

                    audio_bytes = b"".join(audio_buffer)
                    audio_buffer.clear()

                    # ── STT ───────────────────────────────────────────
                    try:
                        transcript = await stt_service.transcribe_audio(
                            audio_bytes,
                            content_type=content_type,
                        )
                    except Exception as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "detail": f"STT error: {exc}"})
                        )
                        continue

                    if not transcript:
                        await websocket.send_text(
                            json.dumps({"type": "error", "detail": "Audio was silent or unclear."})
                        )
                        continue

                    await websocket.send_text(
                        json.dumps({"type": "transcript", "text": transcript})
                    )

                    # ── LLM ───────────────────────────────────────────
                    history = memory_service.get_history(sid)
                    try:
                        llm_result = await llm_service.get_ai_reply(history, transcript)
                    except Exception as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "detail": f"LLM error: {exc}"})
                        )
                        continue

                    memory_service.add_exchange(sid, transcript, llm_result.reply)

                    await websocket.send_text(json.dumps({
                        "type": "reply_text",
                        "text": llm_result.reply,
                        "intent": llm_result.intent,
                        "language": llm_result.language,
                        "emotion": llm_result.emotion,
                    }))

                    # ── TTS stream ────────────────────────────────────
                    try:
                        async for chunk in tts_service.stream_speech(llm_result.reply):
                            await websocket.send_bytes(chunk)
                    except Exception as exc:
                        await websocket.send_text(
                            json.dumps({"type": "error", "detail": f"TTS error: {exc}"})
                        )
                        continue

                    # Turn complete — client may send next utterance
                    await websocket.send_text(json.dumps({"type": "done"}))

                elif msg_type == "disconnect":
                    break

    except (WebSocketDisconnect, RuntimeError):
        pass  # client closed — clean exit

    finally:
        # Nothing to close — WebSocket lifecycle is handled by Starlette
        pass


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
        emotion=llm_result.emotion,
        reply_text=llm_result.reply,
        reply_audio_b64=audio_b64,
        reply_audio_format=settings.TTS_FORMAT if audio_b64 else None,
    )
