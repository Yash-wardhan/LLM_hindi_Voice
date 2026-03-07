from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import auth, health, voice, sessions
from app.core.config import settings
from app.core.database import create_all_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    # Shutdown
    print(f"Shutting down {settings.APP_NAME}")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = f"/api/{settings.API_VERSION}"

    # --- Routers ---
    application.include_router(health.router, tags=["Health"])
    application.include_router(
        auth.router,
        prefix=f"{prefix}/auth",
        tags=["Auth"],
    )
    application.include_router(
        voice.router,
        prefix=f"{prefix}/voice",
        tags=["Voice AI"],
    )
    application.include_router(
        sessions.router,
        prefix=f"{prefix}/sessions",
        tags=["Sessions"],
    )

    return application


app = create_application()

