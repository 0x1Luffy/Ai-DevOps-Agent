"""Database migration runner — applies schema.sql on startup."""

from __future__ import annotations

import pathlib

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

SCHEMA_FILE = pathlib.Path(__file__).parent / "schema.sql"


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Read schema.sql and execute it against the database.

    The schema uses IF NOT EXISTS / CREATE OR REPLACE so it is safe to run
    on every startup.
    """
    logger.info("Running database migrations", schema_file=str(SCHEMA_FILE))
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    async with pool.acquire() as conn:
        await conn.execute(schema_sql)

    logger.info("Database migrations complete")
