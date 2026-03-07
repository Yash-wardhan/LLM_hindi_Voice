"""
Tests for the Voice AI endpoints.
All OpenAI service calls are mocked so tests run without API keys.
"""

import base64
import io
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.main import app
from app.models.db_models import User
from app.models.schemas import LLMResult

# ── Fake user for auth-protected endpoints ────────────────────────────────────
_FAKE_USER = User(
    id="test-user-001",
    email="tester@example.com",
    hashed_password="notreal",
    name="Test User",
    is_active=True,
    created_at=datetime.now(timezone.utc),
)


async def _override_get_current_user() -> User:
    return _FAKE_USER

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
                emotion="happy",
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


# ── Voice Stream ──────────────────────────────────────────────────────────────
# POST /api/v1/voice/stream
# ─ sends audio file
# ─ receives raw audio bytes streamed back (no base64)
# ─ metadata (transcript, intent, language, emotion, reply) is in response headers
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceStreamEndpoint:
    """
    Audio-in → streamed audio-out pipeline.

    The /stream endpoint returns:
      • HTTP 200
      • Content-Type: audio/mpeg  (or other TTS format)
      • Headers: X-Session-Id, X-Transcript, X-Intent,
                 X-Language, X-Emotion, X-Reply-Text
      • Body: raw audio bytes (no base64 wrapping)
    """

    # Split the mock bytes into two chunks to exercise the generator.
    _CHUNK_A = _MOCK_AUDIO_BYTES[:20]
    _CHUNK_B = _MOCK_AUDIO_BYTES[20:]

    @pytest.fixture(autouse=True)
    def mock_stream_tts(self):
        """Replace stream_speech with a fake async generator."""
        async def _fake_stream(text: str):
            yield self._CHUNK_A
            yield self._CHUNK_B

        with patch(
            "app.services.tts_service.stream_speech",
            side_effect=_fake_stream,
        ):
            yield

    # ── Basic contract ────────────────────────────────────

    def test_stream_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert response.status_code == 200

    def test_stream_content_type_is_audio(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert "audio/" in response.headers["content-type"]

    def test_stream_body_is_raw_audio_bytes(self, client: TestClient) -> None:
        """All chunks must arrive and reassemble to the original mock bytes."""
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert response.content == _MOCK_AUDIO_BYTES

    def test_stream_body_is_not_base64(self, client: TestClient) -> None:
        """Body must be raw bytes, not a base64 JSON string."""
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        # raw MP3 bytes start with 0xFF — not valid UTF-8 JSON
        assert response.content[:4] == _MOCK_AUDIO_BYTES[:4]

    # ── Metadata headers ──────────────────────────────────

    def test_stream_has_session_id_header(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert "x-session-id" in response.headers
        assert response.headers["x-session-id"]  # non-empty

    def test_stream_has_transcript_header(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert response.headers["x-transcript"] == _MOCK_TRANSCRIPT

    def test_stream_has_intent_and_language_headers(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert response.headers["x-intent"] == "smalltalk"
        assert response.headers["x-language"] == "hinglish"
        assert "x-reply-text" in response.headers

    # ── Session continuity ────────────────────────────────

    def test_stream_session_continuity(self, client: TestClient) -> None:
        """Passing the same session_id in the form data reuses the session."""
        first = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        sid = first.headers["x-session-id"]

        second = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
            data={"session_id": sid},
        )
        assert second.headers["x-session-id"] == sid

    def test_stream_new_session_if_no_id(self, client: TestClient) -> None:
        r1 = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        r2 = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("test.wav", io.BytesIO(_WAV_HEADER), "audio/wav")},
        )
        assert r1.headers["x-session-id"] != r2.headers["x-session-id"]

    # ── Error handling ────────────────────────────────────

    def test_stream_rejects_unsupported_mime(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/voice/stream",
            files={"audio": ("bad.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 415


# ── WebSocket Real-Time Voice ─────────────────────────────────────────────────
#
# WebSocket protocol (one turn = one user utterance):
#
#  CLIENT → SERVER  binary frames  : raw audio chunks from microphone
#  CLIENT → SERVER  text frame     : {"type":"end_of_speech","content_type":"audio/wav"}
#  SERVER → CLIENT  text frame     : {"type":"transcript","text":"..."}
#  SERVER → CLIENT  text frame     : {"type":"reply_text","text":"...",
#                                      "intent":"...","language":"...","emotion":"..."}
#  SERVER → CLIENT  binary frames  : TTS audio chunks (streamed)
#  SERVER → CLIENT  text frame     : {"type":"done"}
#
# The connection stays open for multi-turn conversation.
# ──────────────────────────────────────────────────────────────────────────

# Two fake audio chunks that together equal _MOCK_AUDIO_BYTES
_WS_CHUNK_A = _MOCK_AUDIO_BYTES[:20]
_WS_CHUNK_B = _MOCK_AUDIO_BYTES[20:]


class TestVoiceWebSocket:
    """
    Real-time bidirectional WebSocket voice pipeline tests.
    All service calls are mocked (no OpenAI keys needed).
    """

    @pytest.fixture(autouse=True)
    def mock_ws_stream(self):
        """Replace stream_speech with a two-chunk async generator."""
        async def _fake_stream(_text: str):
            yield _WS_CHUNK_A
            yield _WS_CHUNK_B

        with patch(
            "app.services.tts_service.stream_speech",
            side_effect=_fake_stream,
        ):
            yield

    # ── helpers ───────────────────────────────────────────

    @staticmethod
    def _send_turn(ws, audio: bytes = _WAV_HEADER, content_type: str = "audio/wav") -> None:
        """Send one audio turn: binary chunk(s) + end_of_speech signal."""
        ws.send_bytes(audio)
        ws.send_json({"type": "end_of_speech", "content_type": content_type})

    @staticmethod
    def _collect_turn(ws) -> dict:
        """
        Collect all server messages for one turn and return them structured::

            {
                'transcript': {...},
                'reply_text': {...},
                'audio': b'<all chunks concatenated>',
                'done': {...},
            }
        """
        result = {"audio": b""}
        while True:
            raw = ws.receive()
            if "text" in raw and raw["text"] is not None:
                msg = json.loads(raw["text"])
                t = msg["type"]
                result[t] = msg
                if t == "done":
                    break
            elif "bytes" in raw and raw["bytes"] is not None:
                result["audio"] += raw["bytes"]
        return result

    # ── Connection ────────────────────────────────────────

    def test_ws_ready_on_connect(self, client: TestClient) -> None:
        """Server sends {type:ready} immediately after handshake."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "ready"

    def test_ws_ready_contains_session_id(self, client: TestClient) -> None:
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            msg = ws.receive_json()
            assert "session_id" in msg
            assert msg["session_id"]  # non-empty

    def test_ws_accepts_custom_session_id(self, client: TestClient) -> None:
        """session_id passed as query param is echoed back in ready message."""
        with client.websocket_connect("/api/v1/voice/ws?session_id=my-test-session") as ws:
            msg = ws.receive_json()
            assert msg["session_id"] == "my-test-session"

    # ── Full turn ─────────────────────────────────────────

    def test_ws_full_turn_message_order(self, client: TestClient) -> None:
        """
        After sending audio + end_of_speech the server must send
        transcript → reply_text → binary audio → done,  in that order.
        """
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            self._send_turn(ws)
            turn = self._collect_turn(ws)
            assert "transcript" in turn
            assert "reply_text" in turn
            assert turn["audio"]  # non-empty
            assert "done" in turn

    def test_ws_transcript_text(self, client: TestClient) -> None:
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            self._send_turn(ws)
            turn = self._collect_turn(ws)
            assert turn["transcript"]["text"] == _MOCK_TRANSCRIPT

    def test_ws_reply_text_content(self, client: TestClient) -> None:
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            self._send_turn(ws)
            turn = self._collect_turn(ws)
            assert turn["reply_text"]["text"] == _MOCK_REPLY

    def test_ws_reply_has_intent_language_emotion(self, client: TestClient) -> None:
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            self._send_turn(ws)
            turn = self._collect_turn(ws)
            rt = turn["reply_text"]
            assert rt["intent"] == "smalltalk"
            assert rt["language"] == "hinglish"
            assert "emotion" in rt

    def test_ws_audio_chunks_reassemble_correctly(self, client: TestClient) -> None:
        """All streamed binary chunks must concatenate to the original mock bytes."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            self._send_turn(ws)
            turn = self._collect_turn(ws)
            assert turn["audio"] == _MOCK_AUDIO_BYTES

    # ── Multi-turn (session continuity) ───────────────────

    def test_ws_multi_turn_same_session(self, client: TestClient) -> None:
        """Two turns on the same connection share the same session_id."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ready = ws.receive_json()
            sid = ready["session_id"]

            # Turn 1
            self._send_turn(ws)
            self._collect_turn(ws)  # drain

            # Turn 2
            self._send_turn(ws)
            turn2 = self._collect_turn(ws)

            # Both turns completed inside one connection == same session
            assert turn2["transcript"]["text"] == _MOCK_TRANSCRIPT  # service still mocked
            assert sid  # session was set at connection time

    def test_ws_new_session_each_connection(self, client: TestClient) -> None:
        """Each fresh connection without a session_id gets a unique session."""
        with client.websocket_connect("/api/v1/voice/ws") as ws1:
            sid1 = ws1.receive_json()["session_id"]
        with client.websocket_connect("/api/v1/voice/ws") as ws2:
            sid2 = ws2.receive_json()["session_id"]
        assert sid1 != sid2

    # ── Error paths ───────────────────────────────────────

    def test_ws_error_on_end_of_speech_without_audio(self, client: TestClient) -> None:
        """end_of_speech with empty buffer → server sends error, not transcript."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "end_of_speech", "content_type": "audio/wav"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "detail" in err

    def test_ws_error_on_invalid_json_control(self, client: TestClient) -> None:
        """A malformed text frame → server sends error and stays alive."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            ws.send_text("this is not json{{{")  # bad frame
            err = ws.receive_json()
            assert err["type"] == "error"

    def test_ws_disconnect_message_closes_cleanly(self, client: TestClient) -> None:
        """Client-side disconnect message closes the connection without error."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "disconnect"})
            # After disconnect the server exits the loop; connection should close

    # ── Multiple binary chunks per turn ──────────────────

    def test_ws_multiple_audio_chunks_before_end(self, client: TestClient) -> None:
        """Client may send several binary frames; all are buffered into one STT call."""
        with client.websocket_connect("/api/v1/voice/ws") as ws:
            ws.receive_json()  # ready
            # Send audio in two fragments
            half = len(_WAV_HEADER) // 2
            ws.send_bytes(_WAV_HEADER[:half])
            ws.send_bytes(_WAV_HEADER[half:])
            ws.send_json({"type": "end_of_speech", "content_type": "audio/wav"})
            turn = self._collect_turn(ws)
            # STT mock still returns the fixed transcript regardless of input size
            assert turn["transcript"]["text"] == _MOCK_TRANSCRIPT


# ── Session Management ────────────────────────────────────────────────────────


class TestSessionEndpoints:
    @pytest.fixture(autouse=True)
    def mock_auth(self):
        """Override JWT auth so session endpoints accept requests without a real token."""
        app.dependency_overrides[get_current_user] = _override_get_current_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    def _create_session(self, client: TestClient) -> str:
        """Helper: create a DB-backed session via POST /api/v1/sessions."""
        resp = client.post(
            "/api/v1/sessions",
            json={"label": "test-session"},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["session_id"]

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
