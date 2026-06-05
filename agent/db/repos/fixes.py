"""Fix-execution repository — async CRUD for fix_executions table."""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def create_fix_execution(pool: asyncpg.Pool, data: dict[str, Any]) -> str:
    """Insert a fix_execution row and return its UUID string."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO fix_executions (
                incident_id, fix_action, fix_params, fix_description,
                kubectl_commands, executed_by, approver_slack_id, result,
                verification_status, error_message, execution_duration_ms
            ) VALUES (
                $1::uuid, $2, $3::jsonb, $4,
                $5, $6, $7, $8,
                $9, $10, $11
            ) RETURNING id
            """,
            data.get("incident_id"),
            data.get("fix_action"),
            json.dumps(data.get("fix_params")) if data.get("fix_params") is not None else None,
            data.get("fix_description"),
            data.get("kubectl_commands"),
            data.get("executed_by", "auto"),
            data.get("approver_slack_id"),
            data.get("result"),
            data.get("verification_status", "pending"),
            data.get("error_message"),
            data.get("execution_duration_ms"),
        )
        fix_id = str(row["id"])
        logger.info(
            "Fix execution recorded",
            fix_id=fix_id,
            action=data.get("fix_action"),
            incident_id=data.get("incident_id"),
        )
        return fix_id


async def update_fix_execution(pool: asyncpg.Pool, fix_id: str, **kwargs: Any) -> None:
    """Update columns of a fix_execution row."""
    set_clauses: list[str] = []
    values: list[Any] = [fix_id]
    idx = 2

    allowed_columns = {
        "result", "verification_status", "verified_at", "error_message",
        "execution_duration_ms", "approver_slack_id", "fix_params",
    }
    json_columns = {"fix_params"}

    for key, value in kwargs.items():
        if key not in allowed_columns:
            continue
        if key in json_columns and value is not None:
            value = json.dumps(value)
            set_clauses.append(f"{key} = ${idx}::jsonb")
        else:
            set_clauses.append(f"{key} = ${idx}")
        values.append(value)
        idx += 1

    if not set_clauses:
        return

    sql = f"UPDATE fix_executions SET {', '.join(set_clauses)} WHERE id = $1::uuid"
    async with pool.acquire() as conn:
        await conn.execute(sql, *values)
    logger.debug("Fix execution updated", fix_id=fix_id, fields=list(kwargs.keys()))


async def list_fix_executions(pool: asyncpg.Pool, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Return fix executions matching the given filters."""
    conditions: list[str] = []
    values: list[Any] = []
    idx = 1

    if filters.get("incident_id"):
        conditions.append(f"incident_id = ${idx}::uuid")
        values.append(filters["incident_id"])
        idx += 1
    if filters.get("result"):
        conditions.append(f"result = ${idx}")
        values.append(filters["result"])
        idx += 1
    if filters.get("since"):
        conditions.append(f"executed_at >= ${idx}")
        values.append(filters["since"])
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM fix_executions {where} ORDER BY executed_at DESC LIMIT 200"

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *values)
    return [dict(r) for r in rows]


async def get_fix_patterns(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Return all fix patterns ordered by success rate descending."""
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
