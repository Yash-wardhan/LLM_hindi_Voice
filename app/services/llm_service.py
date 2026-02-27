"""
LLM service — GPT-4o-mini with Hindi/Hinglish slang awareness.
Returns structured intent + language + reply.
"""

import json
import re
from typing import List

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import LLMResult

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an intelligent AI voice assistant that understands Hindi, English, and Hinglish (Hindi-English mix).

LANGUAGE RULES:
- Detect the language the user is using (hi = Hindi, en = English, hinglish = Hinglish mix).
- Always reply in the SAME language/style the user used.
- If user writes in Hindi script (Devanagari), reply in Hindi.
- If user writes in Roman Hindi (Hinglish), reply in Roman Hindi.
- If user writes in English, reply in English.

HINDI SLANG YOU UNDERSTAND (treat these naturally):
yaar / bhai / dost = friend
kya baat hai / kya scene hai / kya chal raha = what's up / what's happening
thoda = a little | bilkul = absolutely | acha / achha = okay / good
bas = enough / just | mast = awesome / great | bindaas = carefree / cool
sahi hai / sahi bola = that's right | chalo / chalte hain = let's go / okay let's do it
kal karenge = will do tomorrow | abhi nahi = not right now
yaar sun / bhai sun = hey listen | kuch nahi / kuch nahi yaar = nothing / never mind
ekdum = exactly / totally | thik hai = okay / alright
zyada = too much | kam = less | jaldi = quickly | dheere = slowly
khaana = food | paani = water | sona = sleep | uthna = wake up
help karo = help me | batao = tell me | dikhao = show me

INTENT CATEGORIES (pick the closest one):
greeting, question, command, complaint, smalltalk, order, emergency, reminder, weather, joke, other

OUTPUT FORMAT — you MUST return valid JSON only, no extra text:
{
  "intent": "<intent_category>",
  "language": "<hi|en|hinglish>",
  "reply": "<your natural conversational reply>"
}
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
        reply=data.get("reply", raw),  # fall back to raw if parse fails
    )
