"""Async SQLAlchemy session management."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "development",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"timeout": 5},
        )
        logger.info("Database engine created")
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def reset_engine() -> None:
    """Drop the process-global engine and session factory.

    The pooled asyncpg connections belong to whichever event loop created them,
    so they must not be reused after that loop is gone — for example between
    two ``TestClient`` runs.
    """
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Yields:
        An async SQLAlchemy session.

    Example:
        >>> @router.get("/items")
        >>> async def get_items(session: AsyncSession = Depends(get_db_session)):
        >>>     ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
