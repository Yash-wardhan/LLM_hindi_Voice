# AI Voice Assistant API

FastAPI backend with versioned routing, health probes, and a service layer.

---

## Project Structure

```
AI-Voice-Assi/
├── app/
│   ├── main.py                    # App factory, middleware, router registration
│   ├── api/
│   │   └── v1/
│   │       └── routers/
│   │           ├── health.py      # /health  /health/live  /health/ready
│   │           └── example.py    # /api/v1/items  (full CRUD)
│   ├── core/
│   │   ├── config.py              # Settings loaded from .env
│   │   ├── dependencies.py        # Reusable FastAPI Depends (auth)
│   │   └── exceptions.py         # Custom exception classes + handlers
│   ├── models/
│   │   └── schemas.py             # Pydantic v2 request/response schemas
│   └── services/
│       └── example_service.py    # Business logic (swap with DB layer)
├── tests/
│   ├── conftest.py                # Shared pytest fixtures
│   ├── test_health.py             # Health endpoint tests
│   └── test_example.py           # CRUD endpoint tests
├── run.py                         # Uvicorn entry point
├── pytest.ini                     # Pytest config
├── requirements.txt               # Runtime dependencies
├── requirements-dev.txt           # Test/dev dependencies
├── .env.example                   # Environment variable template
└── .gitignore
```

---

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) **or** `pip`

---

## Setup

### 1. Clone & enter the project

```powershell
cd "c:\Users\Admin\Desktop\Assignement\AI-Voice-Assi"
```

### 2. Create & activate a virtual environment (optional but recommended)

```powershell
uv venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
# Runtime
uv pip install -r requirements.txt

# Dev / test
uv pip install -r requirements-dev.txt
```

### 4. Configure environment variables

```powershell
cp .env.example .env
```

Edit `.env` and set your values (especially `SECRET_KEY` for production).

---

## Running the Server

```powershell
# via run.py entry point
uv run python run.py

# or directly with uvicorn (auto-reload for development)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server starts at: **http://localhost:8000**

---

## API Documentation

| UI | URL |
|----|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

## Health Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Full health status + uptime |
| GET | `/health/live` | Liveness probe (process alive?) |
| GET | `/health/ready` | Readiness probe (ready to serve?) |

---

## API Endpoints

All business routes are versioned under `/api/v1`.

### Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/items` | List all items |
| POST | `/api/v1/items` | Create a new item |
| GET | `/api/v1/items/{id}` | Get item by ID |
| PATCH | `/api/v1/items/{id}` | Update item |
| DELETE | `/api/v1/items/{id}` | Delete item |

**Example POST body:**
```json
{
  "name": "My Item",
  "description": "Optional description"
}
```

---

## Running Tests

```powershell
uv run pytest
```

Run with coverage:

```powershell
uv run pytest --cov=app --cov-report=term-missing
```

---

## Postman

Import the base URL `http://localhost:8000` and use the endpoints listed above.
Alternatively, use the built-in **Swagger UI** at `/docs` for instant interactive testing — no Postman setup needed.
