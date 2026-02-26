from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import health, example
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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

    # --- Routers ---
    application.include_router(health.router, tags=["Health"])
    application.include_router(
        example.router,
        prefix=f"/api/{settings.API_VERSION}",
        tags=["Example"],
    )

    return application


app = create_application()
