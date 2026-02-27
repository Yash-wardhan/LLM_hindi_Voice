"""
Text-to-Speech service using OpenAI TTS API.
Returns raw audio bytes (MP3 by default).
"""

from openai import AsyncOpenAI

from app.core.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def synthesize_speech(text: str) -> bytes:
    """
    Convert text to speech audio bytes.

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
