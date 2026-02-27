# AI Voice Assistant API

> Hindi-aware AI Voice Assistant backend -- audio in, voice out.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20|%20GPT--4o%20|%20TTS-412991?logo=openai)
![License](https://img.shields.io/badge/License-MIT-green)

**Pipeline:**
`Audio Upload` -> `Whisper STT` -> `GPT-4o Intent/Reply` -> `OpenAI TTS` -> `Base64 Audio Response`

---

## Features

- **Speech-to-Text** -- OpenAI Whisper (supports Hindi, Hinglish, English)
- **LLM Replies** -- GPT-4o-mini with intent detection and conversation memory
- **Text-to-Speech** -- OpenAI TTS with configurable voice and format
- **Session Management** -- In-memory conversation history with TTL
- **JWT Auth** -- Secure endpoints with Bearer token authentication
- **Interactive Docs** -- Swagger UI & ReDoc out of the box

---

## Project Structure

```
AI-Voice-Assi/
|-- app/
|   |-- main.py                        # App factory, middleware, router wiring
|   |-- api/v1/routers/
|   |   |-- voice.py                   # POST /voice/chat  POST /voice/text-chat
|   |   |-- sessions.py                # GET/DELETE /sessions
|   |   |-- health.py                  # /health  /health/live  /health/ready
|   |   `-- example.py                 # /items CRUD
|   |-- core/
|   |   |-- config.py                  # All settings from .env
|   |   |-- dependencies.py            # Auth Depends
|   |   `-- exceptions.py              # Custom exceptions
|   |-- models/
|   |   `-- schemas.py                 # Pydantic v2 schemas
|   `-- services/
|       |-- stt_service.py             # OpenAI Whisper (Speech -> Text)
|       |-- llm_service.py             # GPT-4o-mini (Intent + Reply)
|       |-- tts_service.py             # OpenAI TTS (Text -> Speech)
|       `-- memory_service.py          # In-memory conversation history
|-- tests/
|   |-- conftest.py
|   |-- test_voice.py                  # Voice + session tests (mocked)
|   |-- test_health.py
|   `-- test_example.py
|-- run.py
|-- requirements.txt
|-- requirements-dev.txt
|-- .env.example                       # Copy to .env and fill in your keys
`-- .gitignore
```

---

## Prerequisites

- Python 3.11+
- `pip` or `uv`
- OpenAI API key: https://platform.openai.com/api-keys

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/AI-Voice-Assi.git
cd AI-Voice-Assi

# 2. Create and activate a virtual environment
python -m venv env

# Windows
env\Scripts\activate
# Linux / macOS
source env/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment variables
cp .env.example .env
# Open .env and set OPENAI_API_KEY=sk-...
```

> **Using `uv`?**
> ```bash
> uv pip install -r requirements.txt
> uv pip install -r requirements-dev.txt
> ```

---

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI (interactive) |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/health | Health check |

---

## API Reference

### Voice AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/voice/chat` | Audio file -> transcript + AI reply + audio |
| POST | `/api/v1/voice/text-chat` | Text message -> AI reply + optional audio |

#### `POST /api/v1/voice/chat` -- multipart/form-data

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio` | file | Yes | wav / mp3 / webm / ogg / m4a / flac (max 25 MB) |
| `session_id` | string | No | Leave blank to start a new conversation |

**Response:**
```json
{
  "session_id": "abc-123",
  "transcript": "yaar kya chal raha hai",
  "intent": "smalltalk",
  "language_detected": "hinglish",
  "reply_text": "Sab badhiya hai bhai!",
  "reply_audio_b64": "<base64 MP3>",
  "reply_audio_format": "mp3"
}
```

#### `POST /api/v1/voice/text-chat` -- application/json

```json
{
  "session_id": "abc-123",
  "message": "kya tum meri help kar sakte ho?",
  "tts": true
}
```

---

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sessions` | List all active sessions |
| GET | `/api/v1/sessions/{id}` | Get session details |
| DELETE | `/api/v1/sessions/{id}` | Clear conversation memory |

---

### Health Probes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Full status + uptime |
| GET | `/health/live` | Liveness (process alive) |
| GET | `/health/ready` | Readiness (services ready) |

---

## Run Tests

All OpenAI calls are mocked -- **no API key needed** for tests.

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing
```

---

## Quick Test

1. Start the server
2. Open http://localhost:8000/docs in your browser
3. Use Swagger UI to upload audio or send a text message directly

Or via `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/voice/text-chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"yaar kya haal hai\", \"tts\": false}"
```

---

## Hindi / Hinglish Intents

`greeting` | `question` | `command` | `complaint` | `smalltalk` | `order` | `emergency` | `reminder` | `weather` | `joke` | `other`

Slang understood: `yaar`, `bhai`, `mast`, `bindaas`, `sahi hai`, `ekdum`, `kya scene hai`, `chalte hain`, and more.

---

## Environment Variables

See [.env.example](.env.example) for all available options.

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `SECRET_KEY` | Yes | JWT signing secret (change in production) |
| `LLM_MODEL` | No | Default: `gpt-4o-mini` |
| `TTS_VOICE` | No | Default: `nova` |
| `STT_LANGUAGE` | No | Leave blank for auto-detect or set `hi` for Hindi |

---

## License

MIT -- feel free to use, modify, and distribute.
