"""
Database session management and connection pooling using SQLAlchemy Async Engine.
"""

from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings | None = None) -> AsyncEngine:
    """Initialize the Async SQLAlchemy engine and session factory."""
    global engine, async_session_factory

    if settings is None:
        settings = get_settings()

    engine = create_async_engine(
        settings.async_database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        echo=False,
    )

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    logger.info("Database async engine initialized successfully.")
    return engine


async def close_db() -> None:
    """Dispose the async engine connection pool."""
    global engine, async_session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("Database async engine disposed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an asynchronous database session."""
    global async_session_factory
    if async_session_factory is None:
        init_db()

    assert async_session_factory is not None
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> bool:
    """Execute a lightweight query (SELECT 1) to verify database connectivity."""
    global engine
    if engine is None:
        init_db()

    assert engine is not None
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
