"""
Text-to-Speech service using OpenAI TTS API.
Returns raw audio bytes (MP3 by default), or streams them chunk by chunk.
"""

from typing import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def synthesize_speech(text: str) -> bytes:
    """
    Convert text to speech audio bytes (full response, not streamed).

    Args:
        text: The text to convert (Hindi, English, or Hinglish).

    Returns:
        Raw audio bytes in the configured format (default: MP3).
    """
    response = await _client.audio.speech.create(
        model=settings.TTS_MODEL,
        voice=settings.TTS_VOICE,   # nova sounds natural for conversational Hindi
        input=text,
        response_format=settings.TTS_FORMAT,
    )
    # AsyncOpenAI returns AsyncHttpxBinaryResponseContent
    return response.content


async def stream_speech(text: str) -> AsyncIterator[bytes]:
    """
    Stream TTS audio as an async generator of raw bytes chunks.

    Yields audio data progressively, so the caller can start playing
    back audio before the full synthesis is complete.

    Args:
        text: The text to convert (Hindi, English, or Hinglish).

    Yields:
        Raw audio byte chunks in the configured format (default: MP3).
    """
    async with _client.audio.speech.with_streaming_response.create(
        model=settings.TTS_MODEL,
        voice=settings.TTS_VOICE,
        input=text,
        response_format=settings.TTS_FORMAT,
    ) as response:
        async for chunk in response.iter_bytes(chunk_size=4096):
            yield chunk
