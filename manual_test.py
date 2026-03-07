"""
manual_test.py  —  Interactive manual test for the AI Voice Assistant API
══════════════════════════════════════════════════════════════════════════

BEFORE RUNNING:
  1. Copy .env.example to .env and set OPENAI_API_KEY=sk-...
  2. Start the server in a separate terminal:
         .\env\Scripts\python.exe run.py
  3. Run this script:
         .\env\Scripts\python.exe manual_test.py

WHAT THIS SCRIPT TESTS:
  Step 1  — Health check
  Step 2  — Signup / Login  (get JWT token)
  Step 3  — Text chat  (no audio file needed)
  Step 4  — Voice chat  (uploads a WAV file, gets MP3 back)
  Step 5  — Voice stream  (uploads a WAV file, streams raw MP3 chunks)
  Step 6  — WebSocket real-time stream  (sends mic audio, gets audio back live)
  Step 7  — Session management  (list / get / delete)
"""

import asyncio
import io
import json
import sys
import wave

import httpx
import websockets

BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"

# ── tiny valid WAV (silent, ~0.1 s) ──────────────────────────────────────────
def _make_wav(seconds: float = 0.1, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    n_frames = int(rate * seconds)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


_WAV = _make_wav()


def _hr(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def _ok(label: str, value) -> None:
    print(f"  ✓  {label}: {value}")


def _fail(label: str, resp: httpx.Response) -> None:
    print(f"  ✗  {label} FAILED  [{resp.status_code}]  {resp.text[:200]}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Health
# ─────────────────────────────────────────────────────────────────────────────
def test_health(client: httpx.Client) -> None:
    _hr("Step 1 — Health check")
    r = client.get(f"{BASE}/health")
    if r.status_code != 200:
        _fail("health", r)
    data = r.json()
    _ok("status", data["status"])
    _ok("version", data["version"])
    _ok("uptime_seconds", data["uptime_seconds"])


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Auth (signup + login)
# ─────────────────────────────────────────────────────────────────────────────
def test_auth(client: httpx.Client) -> str:
    _hr("Step 2 — Auth  (signup → login → /me)")

    email = "manualtest@example.com"
    password = "TestPass123"
    name = "Manual Tester"

    # Signup (ignore 409 if account already exists)
    r = client.post(f"{BASE}/api/v1/auth/signup", json={
        "name": name, "email": email, "password": password,
    })
    if r.status_code == 201:
        _ok("signup", "new account created")
    elif r.status_code == 409:
        _ok("signup", "account already exists — skipping")
    else:
        _fail("signup", r)

    # Login
    r = client.post(f"{BASE}/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    if r.status_code != 200:
        _fail("login", r)
    token = r.json()["access_token"]
    _ok("login", "JWT received")

    # /me
    r = client.get(f"{BASE}/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        _fail("/me", r)
    _ok("/me  name", r.json()["name"])

    return token


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Text chat
# ─────────────────────────────────────────────────────────────────────────────
def test_text_chat(client: httpx.Client) -> str:
    _hr("Step 3 — Text chat  (POST /api/v1/voice/text-chat)")

    r = client.post(f"{BASE}/api/v1/voice/text-chat", json={
        "message": "yaar kya haal hai",
        "tts": True,
    }, timeout=30)
    if r.status_code != 200:
        _fail("text-chat", r)
    data = r.json()
    _ok("session_id", data["session_id"])
    _ok("intent", data["intent"])
    _ok("language_detected", data["language_detected"])
    _ok("reply_text", data["reply_text"][:80])
    _ok("audio_b64 length", f"{len(data['reply_audio_b64'])} chars")
    return data["session_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Voice chat (audio upload → JSON + base64 audio)
# ─────────────────────────────────────────────────────────────────────────────
def test_voice_chat(client: httpx.Client) -> str:
    _hr("Step 4 — Voice chat  (POST /api/v1/voice/chat)")

    r = client.post(
        f"{BASE}/api/v1/voice/chat",
        files={"audio": ("speech.wav", _WAV, "audio/wav")},
        timeout=60,
    )
    if r.status_code != 200:
        _fail("voice-chat", r)
    data = r.json()
    _ok("session_id", data["session_id"])
    _ok("transcript", data["transcript"][:80])
    _ok("intent", data["intent"])
    _ok("reply_text", data["reply_text"][:80])
    _ok("audio_b64 length", f"{len(data['reply_audio_b64'])} chars")
    return data["session_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Voice stream (audio upload → streaming raw MP3 bytes)
# ─────────────────────────────────────────────────────────────────────────────
def test_voice_stream(client: httpx.Client) -> None:
    _hr("Step 5 — Voice stream  (POST /api/v1/voice/stream)")

    total_bytes = 0
    with client.stream(
        "POST",
        f"{BASE}/api/v1/voice/stream",
        files={"audio": ("speech.wav", _WAV, "audio/wav")},
        timeout=60,
    ) as r:
        if r.status_code != 200:
            _fail("voice-stream", r)
        headers = r.headers
        _ok("X-Session-Id", headers.get("x-session-id", "—"))
        _ok("X-Transcript", headers.get("x-transcript", "—")[:80])
        _ok("X-Intent", headers.get("x-intent", "—"))
        _ok("X-Language", headers.get("x-language", "—"))
        _ok("X-Reply-Text", headers.get("x-reply-text", "—")[:80])
        _ok("Content-Type", headers.get("content-type", "—"))

        for chunk in r.iter_bytes():
            total_bytes += len(chunk)

    _ok("streamed audio bytes", total_bytes)

    # Optionally save to disk to play back
    out_path = "stream_reply.mp3"
    with client.stream(
        "POST",
        f"{BASE}/api/v1/voice/stream",
        files={"audio": ("speech.wav", _WAV, "audio/wav")},
        timeout=60,
    ) as r2:
        with open(out_path, "wb") as f:
            for chunk in r2.iter_bytes():
                f.write(chunk)
    _ok("saved audio to", out_path)


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — WebSocket real-time pipeline
# ─────────────────────────────────────────────────────────────────────────────
async def test_websocket() -> None:
    _hr("Step 6 — WebSocket real-time  (WS /api/v1/voice/ws)")

    uri = f"{WS_BASE}/api/v1/voice/ws"
    total_audio = 0

    async with websockets.connect(uri) as ws:
        # ── Connection ──
        ready = json.loads(await ws.recv())
        assert ready["type"] == "ready", f"Expected 'ready', got {ready}"
        sid = ready["session_id"]
        _ok("connected  session_id", sid)

        # ── Turn 1: send audio chunks + end_of_speech ──
        print("\n  [Turn 1]")
        half = len(_WAV) // 2
        await ws.send(_WAV[:half])          # first binary chunk
        await ws.send(_WAV[half:])          # second binary chunk
        await ws.send(json.dumps({          # signal end of this utterance
            "type": "end_of_speech",
            "content_type": "audio/wav",
        }))

        # ── Collect server responses for this turn ──
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                total_audio += len(msg)
                print(f"  ↓ audio chunk  {len(msg)} bytes  "
                      f"(total so far: {total_audio})")
                continue
            data = json.loads(msg)
            t = data["type"]
            if t == "transcript":
                _ok("transcript", data["text"][:80])
            elif t == "reply_text":
                _ok("reply_text", data["text"][:80])
                _ok("intent", data["intent"])
                _ok("language", data["language"])
                _ok("emotion", data["emotion"])
            elif t == "error":
                print(f"  ✗  server error: {data['detail']}")
                break
            elif t == "done":
                _ok("turn 1 done — total audio", f"{total_audio} bytes")
                break

        # ── Turn 2: same session, new utterance ──
        print("\n  [Turn 2 — same session]")
        await ws.send(_WAV)
        await ws.send(json.dumps({"type": "end_of_speech", "content_type": "audio/wav"}))

        turn2_audio = 0
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                turn2_audio += len(msg)
                continue
            data = json.loads(msg)
            if data["type"] == "transcript":
                _ok("turn 2 transcript", data["text"][:80])
            elif data["type"] == "done":
                _ok("turn 2 done — audio", f"{turn2_audio} bytes")
                break
            elif data["type"] == "error":
                print(f"  ✗  error: {data['detail']}")
                break

        # ── Disconnect ──
        await ws.send(json.dumps({"type": "disconnect"}))
        _ok("disconnected cleanly", "✓")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Session management  (requires JWT)
# ─────────────────────────────────────────────────────────────────────────────
def test_sessions(client: httpx.Client, token: str, voice_session_id: str) -> None:
    _hr("Step 7 — Session management")

    auth = {"Authorization": f"Bearer {token}"}

    # Create a named session
    r = client.post(f"{BASE}/api/v1/sessions", json={"label": "manual-test"},
                    headers=auth)
    if r.status_code != 201:
        _fail("create session", r)
    session_id = r.json()["session_id"]
    _ok("created session_id", session_id)

    # List sessions
    r = client.get(f"{BASE}/api/v1/sessions", headers=auth)
    if r.status_code != 200:
        _fail("list sessions", r)
    _ok("total sessions", r.json()["total"])

    # Get session detail
    r = client.get(f"{BASE}/api/v1/sessions/{session_id}", headers=auth)
    if r.status_code != 200:
        _fail("get session", r)
    _ok("session name", r.json()["name"])

    # Delete session
    r = client.delete(f"{BASE}/api/v1/sessions/{session_id}", headers=auth)
    if r.status_code != 204:
        _fail("delete session", r)
    _ok("deleted session", "204 No Content")

    # Confirm gone
    r = client.get(f"{BASE}/api/v1/sessions/{session_id}", headers=auth)
    assert r.status_code == 404, f"Expected 404 after delete, got {r.status_code}"
    _ok("confirmed 404 after delete", "✓")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║        AI Voice Assistant — Manual Test Suite           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Target: {BASE}")

    with httpx.Client() as client:
        # Verify server is up
        try:
            client.get(f"{BASE}/health", timeout=3)
        except httpx.ConnectError:
            print(f"\n  ✗  Cannot connect to {BASE}")
            print("     Start the server first:  .\\env\\Scripts\\python.exe run.py")
            sys.exit(1)

        test_health(client)
        token = test_auth(client)
        text_sid = test_text_chat(client)
        voice_sid = test_voice_chat(client)
        test_voice_stream(client)
        test_sessions(client, token, voice_sid)

    # WebSocket test (async)
    asyncio.run(test_websocket())

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║              All manual tests passed  ✓                 ║")
    print("╚══════════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
