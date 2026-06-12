"""Prometheus metrics endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from db.connection import get_pool

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["observability"])

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

autopilot_incidents_total = Counter(
    "autopilot_incidents_total",
    "Total number of incidents detected",
    ["namespace", "severity", "problem_type"],
)

autopilot_fixes_total = Counter(
    "autopilot_fixes_total",
    "Total number of fix executions",
    ["action", "result"],
)

autopilot_fix_success_rate = Gauge(
    "autopilot_fix_success_rate",
    "Rolling fix success rate (0-1) over last 100 executions",
    ["action"],
)

autopilot_open_incidents = Gauge(
    "autopilot_open_incidents",
    "Current count of open incidents",
    ["severity"],
)

autopilot_scan_duration_seconds = Histogram(
    "autopilot_scan_duration_seconds",
    "Time taken for a full cluster scan cycle",
    buckets=[1, 5, 10, 30, 60, 120],
)

autopilot_diagnosis_duration_seconds = Histogram(
    "autopilot_diagnosis_duration_seconds",
    "Time taken for the LLM provider to return a diagnosis",
    buckets=[0.5, 1, 2, 5, 10, 30],
)

autopilot_jenkins_builds_total = Counter(
    "autopilot_jenkins_builds_total",
    "Jenkins build events processed",
    ["job_name", "failure_type"],
)

autopilot_drift_events_total = Counter(
    "autopilot_drift_events_total",
    "Configuration drift events detected",
    ["namespace", "drift_type"],
)

autopilot_cert_expiry_days = Gauge(
    "autopilot_cert_expiry_days",
    "Days until TLS certificate expiry",
    ["namespace", "secret_name"],
)


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics, enriched with live DB data."""
    pool = await get_pool()

    # Refresh open-incident gauges from DB
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT severity, COUNT(*) AS cnt
                FROM incidents
                WHERE status NOT IN ('fixed', 'escalated', 'manual', 'skipped')
                GROUP BY severity
                """
            )
        for row in rows:
            autopilot_open_incidents.labels(severity=row["severity"]).set(row["cnt"])
    except Exception as exc:
        logger.warning("Metrics: failed to query open incidents", error=str(exc))

    # Refresh fix success rate gauges
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    fix_action,
                    ROUND(100.0 * SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END)
                          / NULLIF(COUNT(*), 0), 2) AS rate
                FROM fix_executions
                WHERE executed_at > NOW() - INTERVAL '7 days'
                GROUP BY fix_action
                """
            )
        for row in rows:
            rate = float(row["rate"] or 0) / 100.0
            autopilot_fix_success_rate.labels(action=row["fix_action"]).set(rate)
    except Exception as exc:
        logger.warning("Metrics: failed to query fix success rate", error=str(exc))

    output = generate_latest()
    return PlainTextResponse(content=output.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
