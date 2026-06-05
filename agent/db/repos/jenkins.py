"""Jenkins-incident repository — async CRUD for jenkins_incidents table."""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)


async def create_jenkins_incident(pool: asyncpg.Pool, data: dict[str, Any]) -> str:
    """Insert a jenkins_incidents row and return its UUID string."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO jenkins_incidents (
                job_name, build_number, branch, commit_sha, failure_type,
                failing_stage, failing_line, ai_diagnosis, action_taken,
                retry_count, resolved, github_issue_url,
                build_duration_seconds, console_log_snippet
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8::jsonb, $9,
                $10, $11, $12,
                $13, $14
            ) RETURNING id
            """,
            data.get("job_name"),
            data.get("build_number"),
            data.get("branch"),
            data.get("commit_sha"),
            data.get("failure_type"),
            data.get("failing_stage"),
            data.get("failing_line"),
            json.dumps(data.get("ai_diagnosis")) if data.get("ai_diagnosis") is not None else None,
            data.get("action_taken"),
            data.get("retry_count", 0),
            data.get("resolved", False),
            data.get("github_issue_url"),
            data.get("build_duration_seconds"),
            data.get("console_log_snippet"),
        )
        incident_id = str(row["id"])
        logger.info(
            "Jenkins incident created",
            incident_id=incident_id,
            job=data.get("job_name"),
            build=data.get("build_number"),
        )
        return incident_id


async def update_jenkins_incident(pool: asyncpg.Pool, incident_id: str, **kwargs: Any) -> None:
    """Update columns of a jenkins_incidents row."""
    set_clauses: list[str] = []
    values: list[Any] = [incident_id]
    idx = 2

    allowed_columns = {
        "failure_type", "failing_stage", "failing_line", "ai_diagnosis",
        "action_taken", "retry_count", "resolved", "resolved_at",
        "github_issue_url", "build_duration_seconds", "console_log_snippet",
    }
    json_columns = {"ai_diagnosis"}

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

    sql = f"UPDATE jenkins_incidents SET {', '.join(set_clauses)} WHERE id = $1::uuid"
    async with pool.acquire() as conn:
        await conn.execute(sql, *values)
    logger.debug("Jenkins incident updated", incident_id=incident_id)


async def list_jenkins_incidents(
    pool: asyncpg.Pool,
    filters: dict[str, Any],
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Return a paginated list of Jenkins incidents with optional filters."""
    conditions: list[str] = []
    values: list[Any] = []
    idx = 1

    if filters.get("job_name"):
        conditions.append(f"job_name = ${idx}")
        values.append(filters["job_name"])
        idx += 1
    if filters.get("resolved") is not None:
        conditions.append(f"resolved = ${idx}")
        values.append(filters["resolved"])
        idx += 1
    if filters.get("failure_type"):
        conditions.append(f"failure_type = ${idx}")
        values.append(filters["failure_type"])
        idx += 1
    if filters.get("since"):
        conditions.append(f"detected_at >= ${idx}")
        values.append(filters["since"])
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit

    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) FROM jenkins_incidents {where}", *values
        )
        total = count_row["count"] if count_row else 0

        rows = await conn.fetch(
            f"SELECT * FROM jenkins_incidents {where} ORDER BY detected_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *values,
            limit,
            offset,
        )

    return [dict(r) for r in rows], int(total)


async def get_pipeline_health(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Return per-job health metrics for the last 7 days."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                job_name,
                COUNT(*) AS total_builds,
                COUNT(*) FILTER (WHERE resolved = TRUE) AS resolved_count,
                COUNT(*) FILTER (WHERE failure_type = 'FLAKY_TEST') AS flaky_count,
                COUNT(*) FILTER (WHERE failure_type = 'REAL_TEST_FAILURE') AS real_failure_count,
                ROUND(
                    100.0 * COUNT(*) FILTER (WHERE resolved = TRUE) / NULLIF(COUNT(*), 0), 1
                ) AS resolve_rate_pct
            FROM jenkins_incidents
            WHERE detected_at > NOW() - INTERVAL '7 days'
            GROUP BY job_name
            ORDER BY total_builds DESC
            """
        )
    return [dict(r) for r in rows]


async def get_flaky_test_patterns(pool: asyncpg.Pool, job_name: str) -> list[dict[str, Any]]:
    """Return recurring flaky test failure patterns for a given job."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                failing_stage,
                COUNT(*) AS occurrence_count,
                MAX(detected_at) AS last_seen,
                ARRAY_AGG(DISTINCT build_number ORDER BY build_number DESC) AS build_numbers
            FROM jenkins_incidents
            WHERE job_name = $1
              AND failure_type = 'FLAKY_TEST'
              AND detected_at > NOW() - INTERVAL '30 days'
            GROUP BY failing_stage
            HAVING COUNT(*) >= 2
            ORDER BY occurrence_count DESC
            """,
            job_name,
        )
    return [dict(r) for r in rows]
