"""
Tests for the Voice AI endpoints.
All OpenAI service calls are mocked so tests run without API keys.
"""

import base64
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import LLMResult

# ── Shared mock audio bytes (silent WAV, 44 bytes) ───────────────────────────
_WAV_HEADER = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    b"\x01\x00\x01\x00\x80\xbb\x00\x00\x00w\x01\x00"
    b"\x02\x00\x10\x00data\x00\x00\x00\x00"
)

_MOCK_TRANSCRIPT = "yaar kya chal raha hai"
_MOCK_REPLY = "Sab badhiya hai bhai! Tera kya haal hai?"
_MOCK_AUDIO_BYTES = b"\xff\xfb\x90\x00" * 10  # fake MP3 bytes


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_openai_services():
    """
    Patch all three OpenAI service calls globally for every voice test.
    """
    with (
        patch(
            "app.services.stt_service.transcribe_audio",
            new_callable=AsyncMock,
            return_value=_MOCK_TRANSCRIPT,
        ) as mock_stt,
        patch(
            "app.services.llm_service.get_ai_reply",
            new_callable=AsyncMock,
            return_value=LLMResult(
                intent="smalltalk",
                language="hinglish",
                reply=_MOCK_REPLY,
            ),
        ) as mock_llm,
        patch(
            "app.services.tts_service.synthesize_speech",
            new_callable=AsyncMock,
            return_value=_MOCK_AUDIO_BYTES,
        ) as mock_tts,
    ):
        yield {"stt": mock_stt, "llm": mock_llm, "tts": mock_tts}


# ── Voice Chat (audio upload) ─────────────────────────────────────────────────

class TestVoiceChatEndpoint:
    def test_voice_chat_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert response.status_code == 200

    def test_voice_chat_response_schema(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        data = response.json()
        assert "session_id" in data
        assert data["transcript"] == _MOCK_TRANSCRIPT
        assert data["reply_text"] == _MOCK_REPLY
        assert data["intent"] == "smalltalk"
        assert data["language_detected"] == "hinglish"
        assert "reply_audio_b64" in data

    def test_voice_chat_audio_is_valid_base64(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        b64 = response.json()["reply_audio_b64"]
        decoded = base64.b64decode(b64)
        assert decoded == _MOCK_AUDIO_BYTES

    def test_voice_chat_session_continuity(self, client: TestClient) -> None:
        """Second request with the same session_id should reuse the session."""
        first = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        ).json()
        sid = first["session_id"]

        second = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
            data={"session_id": sid},
        ).json()
        assert second["session_id"] == sid

    def test_voice_chat_rejects_unsupported_mime(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 415

    def test_voice_chat_new_session_if_no_id(self, client: TestClient) -> None:
        r1 = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        ).json()
        r2 = client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        ).json()
        assert r1["session_id"] != r2["session_id"]


# ── Text Chat ─────────────────────────────────────────────────────────────────

class TestTextChatEndpoint:
    def test_text_chat_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/text-chat",
            json={"message": "yaar kya chal raha hai"},
        )
        assert response.status_code == 200

    def test_text_chat_response_schema(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/text-chat",
            json={"message": "hello"},
        )
        data = response.json()
        assert "session_id" in data
        assert "reply_text" in data
        assert "intent" in data

    def test_text_chat_no_tts(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/text-chat",
            json={"message": "hello", "tts": False},
        )
        data = response.json()
        assert data["reply_audio_b64"] is None

    def test_text_chat_with_tts(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/text-chat",
            json={"message": "hello", "tts": True},
        )
        data = response.json()
        assert data["reply_audio_b64"] is not None


# ── Session Management ────────────────────────────────────────────────────────

class TestSessionEndpoints:
    def _create_session(self, client: TestClient) -> str:
        """Helper: create a voice chat session and return session_id."""
        return client.post(
            "/api/v1/voice/chat",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        ).json()["session_id"]

    def test_list_sessions(self, client: TestClient) -> None:
        response = client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data

    def test_get_existing_session(self, client: TestClient) -> None:
        sid = self._create_session(client)
        response = client.get(f"/api/v1/sessions/{sid}")
        assert response.status_code == 200
        assert response.json()["session_id"] == sid

    def test_get_nonexistent_session(self, client: TestClient) -> None:
        response = client.get("/api/v1/sessions/does-not-exist")
        assert response.status_code == 404

    def test_delete_session(self, client: TestClient) -> None:
        sid = self._create_session(client)
        assert client.delete(f"/api/v1/sessions/{sid}").status_code == 204
        # After delete, session should be gone
        assert client.get(f"/api/v1/sessions/{sid}").status_code == 404

    def test_delete_nonexistent_session(self, client: TestClient) -> None:
        response = client.delete("/api/v1/sessions/ghost-session")
        assert response.status_code == 404
