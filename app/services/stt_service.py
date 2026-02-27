"""
Speech-to-Text service using OpenAI Whisper API.
Supports: Hindi, English, Hinglish, and 99 other languages automatically.
"""

import io
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Audio MIME type → file extension mapping for Whisper
_MIME_TO_EXT: dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
}


async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/webm",
    language: Optional[str] = None,
) -> str:
    """
    Transcribe audio bytes to text.

    Args:
        audio_bytes:  Raw audio bytes from the uploaded file.
        content_type: MIME type of the audio (e.g. "audio/webm").
        language:     BCP-47 language code hint (e.g. "hi" for Hindi).
                      Pass None for automatic detection.

    Returns:
        Transcribed text string.
    """
    ext = _MIME_TO_EXT.get(content_type.lower(), "webm")
    filename = f"audio.{ext}"

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename  # Whisper SDK reads the name to infer format

    # Resolve language: explicit arg → env config → auto-detect
    lang = language or settings.STT_LANGUAGE or None

    response = await _client.audio.transcriptions.create(
        model=settings.STT_MODEL,
        file=audio_file,
        language=lang,         # None = auto-detect across 99 languages
        response_format="text",
        prompt=(
            "यह एक Hindi, English, या Hinglish conversation है। "
            "Slang aur colloquial words ko accurately transcribe karo."
        ),  # Biases Whisper toward Hindi/Hinglish vocabulary
    )

    return str(response).strip()
