from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────
    APP_NAME: str = "AI Voice Assistant API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Hindi-aware AI Voice Assistant — STT → LLM → TTS pipeline"
    API_VERSION: str = "v1"
    DEBUG: bool = False

    # ── Server ─────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── CORS ───────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ── Database (extend as needed) ────────────────────────
    DATABASE_URL: str = "sqlite:///./dev.db"

    # ── Security ───────────────────────────────────────────
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── OpenAI ─────────────────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── STT (Whisper) ──────────────────────────────────────
    STT_MODEL: str = "whisper-1"
    # Force language code e.g. "hi" for Hindi, or leave blank for auto-detect
    STT_LANGUAGE: str = ""

    # ── LLM ────────────────────────────────────────────────
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 500

    # ── TTS ────────────────────────────────────────────────
    TTS_MODEL: str = "tts-1"
    # alloy | echo | fable | onyx | nova | shimmer
    TTS_VOICE: str = "nova"
    TTS_FORMAT: Literal["mp3", "opus", "aac", "flac"] = "mp3"

    # ── Conversation Memory ────────────────────────────────
    MEMORY_MAX_MESSAGES: int = 20       # per session (user+assistant pairs)
    MEMORY_SESSION_TTL_MINUTES: int = 60

    # ── Audio Upload ───────────────────────────────────────
    AUDIO_MAX_SIZE_MB: int = 25
    AUDIO_ALLOWED_TYPES: List[str] = [
        "audio/wav", "audio/mpeg", "audio/mp4", "audio/webm",
        "audio/ogg", "audio/flac", "audio/x-m4a", "audio/mp3",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()

