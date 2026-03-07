from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Health ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    timestamp: str
    uptime_seconds: float


# ── Item (example resource) ──────────────────────────────────────────────────



class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)




# ── Voice / Conversation ─────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class VoiceChatResponse(BaseModel):
    session_id: str = Field(..., description="Session ID for conversation continuity")
    transcript: str = Field(..., description="What the user said (STT output)")
    intent: str = Field(..., description="Detected intent category")
    language_detected: str = Field(..., description="Detected language code: en | hi | hinglish")
    emotion: str = Field(default="neutral", description="Detected emotional tone (e.g. happy, sad, excited)")
    reply_text: str = Field(..., description="AI generated reply (text)")
    reply_audio_b64: str = Field(..., description="Base64-encoded MP3 audio of the reply")
    reply_audio_format: str = Field(default="mp3")


class TextChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Leave blank to start a new session")
    message: str = Field(..., min_length=1, max_length=2000, description="User message text")
    tts: bool = Field(default=True, description="Whether to generate voice reply")


class TextChatResponse(BaseModel):
    session_id: str
    intent: str
    language_detected: str
    emotion: str = Field(default="neutral", description="Detected emotional tone (e.g. happy, sad, excited)")
    reply_text: str
    reply_audio_b64: Optional[str] = None
    reply_audio_format: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Alice"])
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    created_at: str


# ── Session ──────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    label: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional session label / topic (e.g. 'Morning chat'). Defaults to your name.",
        examples=["Morning chat"],
    )


class CreateSessionResponse(BaseModel):
    session_id: str = Field(..., description="UUIDv7 that identifies this session")
    user_id: str
    name: str = Field(..., description="Label stored for this session")


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    name: str
    message_count: int
    last_access: Optional[str] = None
    created_at: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]
    total: int


class LLMResult(BaseModel):
    """Internal model returned by the LLM service."""
    intent: str
    language: str
    emotion: str = "neutral"
    reply: str
    

