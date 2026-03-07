"""
LLM service — GPT-4o-mini with Hindi/Hinglish slang awareness.
Returns structured intent + language + reply.
"""

import json
import re
from pathlib import Path
from typing import List

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import LLMResult

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ── Slang Loader ──────────────────────────────────────────────────────────────

_SLANG_FILE = Path(__file__).parent.parent / "data" / "hinglish_slang.txt"


def _load_slang() -> str:
    """
    Read hinglish_slang.txt and return non-comment, non-empty lines
    joined as a single string block for the system prompt.
    Silently returns an empty string if the file is missing.
    """
    if not _SLANG_FILE.exists():
        return ""
    lines = []
    for raw in _SLANG_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return "\n".join(lines)


_SLANG_BLOCK = _load_slang()

# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = f"""\
You are an intelligent AI voice assistant that understands Hindi, English, and Hinglish (Hindi-English mix).

LANGUAGE RULES:
- Detect the language the user is using (hi = Hindi, en = English, hinglish = Hinglish mix).
- Always reply in the SAME language/style the user used.
- If user writes in Hindi script (Devanagari), reply in Hindi.
- If user writes in Roman Hindi (Hinglish), reply in Roman Hindi.
- If user writes in English, reply in English.

HINDI / HINGLISH SLANG YOU UNDERSTAND (treat these naturally):
{_SLANG_BLOCK}

INTENT CATEGORIES (pick the closest one):
greeting, question, command, complaint, smalltalk, order, emergency, reminder, weather, joke, other

EMOTION DETECTION — identify the emotional tone of the USER's message (not the assistant):
happy      — joy, excitement, satisfaction (e.g. "mast hai!", "bahut acha!")
sad        — sorrow, disappointment (e.g. "bahut bura laga", "I'm feeling down")
angry      — frustration, irritation (e.g. "yaar kya bakwaas hai", "this is so annoying")
excited    — enthusiasm, eagerness (e.g. "woooo!", "itna excited hoon")
fearful    — worry, anxiety (e.g. "dar lag raha hai", "I'm scared")
surprised  — astonishment (e.g. "kya! seriously?", "No way!")
disgusted  — revulsion (e.g. "yuck", "bahut ganda hai")
confused   — uncertainty (e.g. "samajh nahi aaya", "what do you mean?")
empathetic — caring, supportive tone (e.g. "I understand", "bura laga sunke")
neutral    — no strong emotion detected

Your REPLY must also mirror/respond to the user's emotion naturally:
- If user is happy → respond with energy and warmth.
- If user is sad → respond with empathy and comfort.
- If user is angry → respond calmly and acknowledgeingly.
- If user is excited → match their enthusiasm.
- If user is confused → respond with clarity and patience.

OUTPUT FORMAT — you MUST return valid JSON only, no extra text:
{{
  "intent": "<intent_category>",
  "language": "<hi|en|hinglish>",
  "emotion": "<detected_emotion>",
  "reply": "<your natural conversational reply that reflects the user's emotional state>"
}}
"""


# ── Service Function ──────────────────────────────────────────────────────────

async def get_ai_reply(
    session_history: List[dict],
    user_message: str,
) -> LLMResult:
    """
    Generate an AI reply with intent detection.

    Args:
        session_history: List of {"role": ..., "content": ...} dicts.
        user_message:    The latest user message (text).

    Returns:
        LLMResult with intent, language, and reply.
    """
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(session_history)
    messages.append({"role": "user", "content": user_message})

    response = await _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"},  # forces JSON output
    )

    raw = response.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON block from the string
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group()) if match else {}

    return LLMResult(
        intent=data.get("intent", "other"),
        language=data.get("language", "en"),
        emotion=data.get("emotion", "neutral"),
        reply=data.get("reply", raw),  # fall back to raw if parse fails
    )
