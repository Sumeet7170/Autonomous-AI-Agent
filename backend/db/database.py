"""
SQLAlchemy async database setup.
Uses SQLite for development, PostgreSQL for production.
Swap via DATABASE_URL in .env — zero code changes needed.

Async SQLAlchemy lets us use `async with` sessions without blocking the event loop.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
IS_SQLITE = "sqlite" in settings.DATABASE_URL

if IS_SQLITE:
    # SQLite + aiosqlite doesn't support real connection pooling — use NullPool
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,        # Print SQL queries in debug mode
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
    )

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base Class ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


# ── Dependency (for FastAPI route injection) ──────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session per request.

    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables on startup. Safe to call multiple times (no-op if tables exist)."""
    from db import models  # noqa: F401 — imports trigger table registration
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized", url=settings.DATABASE_URL)
