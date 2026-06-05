"""Fix-pattern repository — async operations on the fix_patterns table."""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def record_fix_attempt(
    pool: asyncpg.Pool,
    problem_pattern: str,
    fix_action: str,
    success: bool,
) -> None:
    """Upsert a fix-pattern row, incrementing the success or failure counter."""
    if success:
        sql = """
            INSERT INTO fix_patterns (problem_pattern, fix_action, success_count, last_used)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (problem_pattern, fix_action)
            DO UPDATE SET
                success_count = fix_patterns.success_count + 1,
                last_used = NOW()
        """
    else:
        sql = """
            INSERT INTO fix_patterns (problem_pattern, fix_action, failure_count, last_used)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (problem_pattern, fix_action)
            DO UPDATE SET
                failure_count = fix_patterns.failure_count + 1,
                last_used = NOW()
        """

    async with pool.acquire() as conn:
        await conn.execute(sql, problem_pattern, fix_action)

    logger.debug(
        "Fix attempt recorded",
        problem_pattern=problem_pattern,
        fix_action=fix_action,
        success=success,
    )


async def get_patterns(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Return all fix-pattern rows ordered by success rate descending."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                problem_pattern,
                fix_action,
                success_count,
                failure_count,
                last_used,
                CASE
                    WHEN (success_count + failure_count) = 0 THEN 0
                    ELSE ROUND(100.0 * success_count / (success_count + failure_count), 1)
                END AS success_rate
            FROM fix_patterns
            ORDER BY success_rate DESC, success_count DESC
            """
        )
    return [dict(r) for r in rows]
