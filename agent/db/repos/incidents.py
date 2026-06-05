"""Incident repository — async CRUD operations against the incidents table."""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def create_incident(pool: asyncpg.Pool, data: dict[str, Any]) -> str:
    """Insert a new incident row and return its UUID string."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO incidents (
                resource_type, resource_name, namespace, problem_type, severity,
                root_cause, confidence, auto_fixable, fix_plan, prevention_tip,
                estimated_recovery, related_resources, status, slack_message_ts,
                slack_channel, claude_prompt, claude_response, full_context
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9::jsonb, $10,
                $11, $12::jsonb, $13, $14,
                $15, $16, $17, $18::jsonb
            ) RETURNING id
            """,
            data.get("resource_type"),
            data.get("resource_name"),
            data.get("namespace"),
            data.get("problem_type"),
            data.get("severity", "MEDIUM"),
            data.get("root_cause"),
            data.get("confidence"),
            data.get("auto_fixable", False),
            json.dumps(data.get("fix_plan")) if data.get("fix_plan") is not None else None,
            data.get("prevention_tip"),
            data.get("estimated_recovery"),
            json.dumps(data.get("related_resources")) if data.get("related_resources") is not None else None,
            data.get("status", "open"),
            data.get("slack_message_ts"),
            data.get("slack_channel"),
            data.get("claude_prompt"),
            data.get("claude_response"),
            json.dumps(data.get("full_context")) if data.get("full_context") is not None else None,
        )
        incident_id = str(row["id"])
        logger.info("Incident created", incident_id=incident_id, resource=data.get("resource_name"))
        return incident_id


async def get_incident(pool: asyncpg.Pool, incident_id: str) -> dict[str, Any]:
    """Fetch a single incident by UUID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1::uuid",
            incident_id,
        )
        if row is None:
            return {}
        return dict(row)


async def update_incident_status(
    pool: asyncpg.Pool,
    incident_id: str,
    status: str,
    **kwargs: Any,
) -> None:
    """Update the status (and any extra columns) of an incident."""
    set_clauses = ["status = $2"]
    values: list[Any] = [incident_id, status]
    idx = 3

    allowed_columns = {
        "root_cause", "confidence", "auto_fixable", "fix_plan", "prevention_tip",
        "estimated_recovery", "related_resources", "resolved_at", "slack_message_ts",
        "slack_channel", "claude_prompt", "claude_response", "full_context",
    }
    json_columns = {"fix_plan", "related_resources", "full_context"}

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

    sql = f"UPDATE incidents SET {', '.join(set_clauses)} WHERE id = $1::uuid"
    async with pool.acquire() as conn:
        await conn.execute(sql, *values)
    logger.debug("Incident status updated", incident_id=incident_id, status=status)


async def get_open_incident(
    pool: asyncpg.Pool,
    resource_type: str,
    resource_name: str,
    namespace: str,
    problem_type: str,
) -> dict[str, Any] | None:
    """Return an existing open incident for the same resource + problem (deduplication)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM incidents
            WHERE resource_type = $1
              AND resource_name = $2
              AND namespace = $3
              AND problem_type = $4
              AND status NOT IN ('fixed', 'escalated', 'manual', 'skipped')
            ORDER BY detected_at DESC
            LIMIT 1
            """,
            resource_type,
            resource_name,
            namespace,
            problem_type,
        )
        return dict(row) if row else None


async def list_incidents(
    pool: asyncpg.Pool,
    filters: dict[str, Any],
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Return a paginated list of incidents with optional filters.

    Returns (rows, total_count).
    """
    conditions: list[str] = []
    values: list[Any] = []
    idx = 1

    if filters.get("status"):
        conditions.append(f"status = ${idx}")
        values.append(filters["status"])
        idx += 1
    if filters.get("namespace"):
        conditions.append(f"namespace = ${idx}")
        values.append(filters["namespace"])
        idx += 1
    if filters.get("severity"):
        conditions.append(f"severity = ${idx}")
        values.append(filters["severity"])
        idx += 1
    if filters.get("since"):
        conditions.append(f"detected_at >= ${idx}")
        values.append(filters["since"])
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit

    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(f"SELECT COUNT(*) FROM incidents {where}", *values)
        total = count_row["count"] if count_row else 0

        rows = await conn.fetch(
            f"SELECT * FROM incidents {where} ORDER BY detected_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *values,
            limit,
            offset,
        )

    return [dict(r) for r in rows], int(total)


async def get_incident_stats(pool: asyncpg.Pool) -> dict[str, Any]:
    """Return aggregate statistics for the dashboard / health-gate."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                COUNT(*) FILTER (WHERE status NOT IN ('fixed','escalated','manual','skipped'))          AS open_count,
                COUNT(*) FILTER (WHERE status = 'fixed' AND resolved_at > NOW() - INTERVAL '24h')       AS fixed_24h,
                COUNT(*) FILTER (WHERE severity = 'CRITICAL' AND status NOT IN ('fixed','escalated','manual','skipped')) AS critical_open,
                COUNT(*) FILTER (WHERE severity = 'HIGH' AND status NOT IN ('fixed','escalated','manual','skipped'))    AS high_open,
                COUNT(*) FILTER (WHERE detected_at > NOW() - INTERVAL '24h')                           AS total_24h
            FROM incidents
            """
        )
        stats = dict(rows[0]) if rows else {}

        # Severity breakdown for open incidents
        breakdown_rows = await conn.fetch(
            """
            SELECT severity, COUNT(*) AS cnt
            FROM incidents
            WHERE status NOT IN ('fixed','escalated','manual','skipped')
            GROUP BY severity
            """
        )
        stats["severity_breakdown"] = {r["severity"]: r["cnt"] for r in breakdown_rows}

        # Namespace breakdown
        ns_rows = await conn.fetch(
            """
            SELECT namespace, COUNT(*) AS cnt
            FROM incidents
            WHERE detected_at > NOW() - INTERVAL '24h'
            GROUP BY namespace
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
        stats["namespace_breakdown"] = [dict(r) for r in ns_rows]

    return stats
