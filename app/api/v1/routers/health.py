import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.schemas import HealthResponse

router = APIRouter()

# Track startup time for uptime calculation
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the current health status of the API.",
)
async def health_check() -> HealthResponse:
    uptime_seconds = round(time.time() - _start_time, 2)
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=uptime_seconds,
    )


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Kubernetes liveness probe — confirms the process is alive.",
)
async def liveness() -> JSONResponse:
    return JSONResponse(content={"status": "alive"})


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Kubernetes readiness probe — confirms the app is ready to serve traffic.",
)
async def readiness() -> JSONResponse:
    # TODO: add real checks (DB ping, cache ping, etc.)
    checks = {
        "database": "ok",   # replace with actual DB check
        "cache": "ok",      # replace with actual cache check
    }
    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
