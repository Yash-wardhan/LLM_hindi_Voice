"""
Async SQLAlchemy database setup.
Default: SQLite via aiosqlite (zero-config for development).
For production swap DATABASE_URL to postgresql+asyncpg://...
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Convert plain sqlite:/// → sqlite+aiosqlite:/// for async driver
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("sqlite:///"):
    _db_url = _raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
elif _raw_url.startswith("postgresql://"):
    _db_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    _db_url = _raw_url

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,       # logs SQL when DEBUG=true
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_db():
    """Yield an async DB session; rolls back on error, always closes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ── Startup helper ────────────────────────────────────────────────────────────

async def create_all_tables() -> None:
    """Create all tables defined in ORM models (idempotent)."""
    # Import models so their metadata is registered before create_all
    import app.models.db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
