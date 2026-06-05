"""asyncpg connection pool singleton."""

from __future__ import annotations

import asyncpg
import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton asyncpg connection pool, creating it if necessary."""
    global _pool
    if _pool is None:
        logger.info("Creating asyncpg connection pool", dsn=settings.DATABASE_URL)
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("asyncpg pool created")
    return _pool


async def close_pool() -> None:
    """Close the connection pool gracefully on application shutdown."""
    global _pool
    if _pool is not None:
        logger.info("Closing asyncpg connection pool")
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
