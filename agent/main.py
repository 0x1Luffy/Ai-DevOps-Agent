"""AutoPilot DevOps Agent — main entry point."""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import threading
from typing import Any

import redis.asyncio as aioredis
import structlog
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure structured logging early
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


async def process_incident_queue(redis_client: aioredis.Redis) -> None:
    """
    Continuously pop incidents from the Redis queue, diagnose, and (if auto-fixable)
    execute fixes. This loop runs for the lifetime of the process.
    """
    from core.diagnoser import DiagnoserEngine, IncidentEvent
    from core.executor import FixExecutor
    from core.learning import LearningEngine
    from integrations.slack import SlackIntegration
    from db.repos.incidents import update_incident_status
    from db.connection import get_pool

    diagnoser = DiagnoserEngine()
    executor = FixExecutor()
    learner = LearningEngine()
    slack: SlackIntegration | None = None

    try:
        from config.settings import settings
        if settings.SLACK_BOT_TOKEN:
            slack = SlackIntegration()
    except Exception as exc:
        logger.warning("Slack integration unavailable", error=str(exc))

    logger.info("Incident processing loop started")

    while True:
        try:
            # Blocking pop with 2s timeout so we can catch shutdown signals
            item = await redis_client.brpop("autopilot:incident_queue", timeout=2)
            if item is None:
                continue

            _, raw = item
            data = json.loads(raw)

            logger.info(
                "Processing incident from queue",
                resource=data.get("resource_name"),
                problem=data.get("problem_type"),
            )

            incident = IncidentEvent(**data)

            # Diagnose
            try:
                diagnosis = await diagnoser.diagnose(incident)
            except Exception as exc:
                logger.error("Diagnosis failed", resource=incident.resource_name, error=str(exc))
                continue

            # Send Slack alert for all diagnosed incidents
            if slack:
                try:
                    incident_dict = {
                        "id": diagnosis.incident_id,
                        "severity": diagnosis.severity,
                        "namespace": incident.namespace,
                        "resource_name": incident.resource_name,
                        "problem_type": incident.problem_type,
                    }
                    diag_dict = {
                        "root_cause": diagnosis.root_cause,
                        "confidence": diagnosis.confidence,
                        "fix_plan": [s.model_dump() for s in diagnosis.fix_plan],
                        "prevention_tip": diagnosis.prevention_tip,
                        "estimated_recovery": diagnosis.estimated_recovery,
                    }

                    if not diagnosis.auto_fixable:
                        # CRITICAL / needs approval → send approval request
                        ts, channel = slack.send_approval_request(incident_dict, diag_dict)
                        if ts:
                            pool = await get_pool()
                            await update_incident_status(
                                pool,
                                diagnosis.incident_id,
                                "needs_approval",
                                slack_message_ts=ts,
                                slack_channel=channel,
                            )

                        # Escalate CRITICAL via email
                        if diagnosis.severity == "CRITICAL":
                            try:
                                from integrations.email import EmailIntegration
                                email = EmailIntegration()
                                await email.send_escalation_email(
                                    subject=f"[CRITICAL] {incident.problem_type} — {incident.namespace}/{incident.resource_name}",
                                    body=diagnosis.root_cause,
                                    incident=incident_dict,
                                )
                            except Exception as email_exc:
                                logger.warning("Escalation email failed", error=str(email_exc))
                    else:
                        ts = slack.send_alert(incident_dict, diag_dict)
                except Exception as slack_exc:
                    logger.warning("Slack notification failed", error=str(slack_exc))

            # Execute fix if auto-fixable
            if diagnosis.auto_fixable and diagnosis.fix_plan:
                logger.info(
                    "Executing auto-fix",
                    incident_id=diagnosis.incident_id,
                    steps=len(diagnosis.fix_plan),
                )
                fix_plan_dicts = [s.model_dump() for s in diagnosis.fix_plan]
                try:
                    results = await executor.execute_fix_plan(
                        diagnosis.incident_id, fix_plan_dicts
                    )
                    # Record outcomes in learning engine
                    for result in results:
                        await learner.record_outcome(
                            problem_pattern=incident.problem_type,
                            fix_action=result.action,
                            success=result.success,
                        )
                except Exception as exec_exc:
                    logger.error("Fix execution failed", error=str(exec_exc))

        except asyncio.CancelledError:
            logger.info("Incident queue loop cancelled")
            break
        except Exception as exc:
            logger.exception("Unexpected error in incident processing loop", error=str(exc))
            await asyncio.sleep(1)


async def main() -> None:
    """Application startup, scheduler setup, and graceful shutdown."""
    from config.settings import settings
    from db.connection import close_pool, get_pool
    from db.migrations import run_migrations
    from core.scanner import ClusterScanner
    from watchers.drift_detector import DriftDetector
    from watchers.expiry_watcher import ExpiryWatcher
    from watchers.resource_advisor import ResourceAdvisor

    logger.info("AutoPilot DevOps Agent starting", version="1.0.0")

    # ----------------------------------------------------------------
    # 1. Database setup
    # ----------------------------------------------------------------
    pool = await get_pool()
    await run_migrations(pool)
    logger.info("Database ready")

    # ----------------------------------------------------------------
    # 2. Redis
    # ----------------------------------------------------------------
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_client.ping()
        logger.info("Redis connected", url=settings.REDIS_URL)
    except Exception as exc:
        logger.error("Redis connection failed", error=str(exc))
        sys.exit(1)

    # ----------------------------------------------------------------
    # 3. Scheduler
    # ----------------------------------------------------------------
    scheduler = AsyncIOScheduler()

    scanner = ClusterScanner()
    drift_detector = DriftDetector()
    expiry_watcher = ExpiryWatcher()
    resource_advisor = ResourceAdvisor()

    scheduler.add_job(
        scanner.scan_all_namespaces,
        "interval",
        seconds=settings.SCAN_INTERVAL_SECONDS,
        id="cluster_scan",
        name="Cluster scanner",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        drift_detector.check_drift,
        "interval",
        seconds=300,
        id="drift_check",
        name="Drift detector",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        expiry_watcher.check_tls_certs,
        "interval",
        hours=6,
        id="tls_expiry_check",
        name="TLS expiry watcher",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        resource_advisor.generate_weekly_report,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_right_sizing",
        name="Weekly right-sizing report",
        max_instances=1,
    )

    scheduler.start()
    logger.info("APScheduler started with all jobs")

    # ----------------------------------------------------------------
    # 4. Slack Bolt (background thread)
    # ----------------------------------------------------------------
    if settings.SLACK_BOT_TOKEN:
        try:
            from integrations.slack import SlackIntegration
            slack = SlackIntegration()
            slack.start_background()
        except Exception as exc:
            logger.warning("Slack Bolt failed to start", error=str(exc))
    else:
        logger.warning("SLACK_BOT_TOKEN not set — Slack integration disabled")

    # ----------------------------------------------------------------
    # 5. Incident processing loop (as asyncio task)
    # ----------------------------------------------------------------
    queue_task = asyncio.ensure_future(process_incident_queue(redis_client))

    # ----------------------------------------------------------------
    # 6. FastAPI server
    # ----------------------------------------------------------------
    from api.main import app

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=settings.API_PORT,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    # ----------------------------------------------------------------
    # 7. Graceful shutdown handler
    # ----------------------------------------------------------------
    shutdown_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Shutdown signal received", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))

    # Start API server in background task
    api_task = asyncio.ensure_future(server.serve())

    logger.info(
        "AutoPilot DevOps Agent fully started",
        api_port=settings.API_PORT,
        scan_interval=settings.SCAN_INTERVAL_SECONDS,
        dry_run=settings.DRY_RUN,
    )

    # Block until shutdown signal
    await shutdown_event.wait()

    # ----------------------------------------------------------------
    # 8. Cleanup
    # ----------------------------------------------------------------
    logger.info("Shutting down gracefully...")

    queue_task.cancel()
    try:
        await queue_task
    except asyncio.CancelledError:
        pass

    scheduler.shutdown(wait=False)
    server.should_exit = True
    await api_task

    await redis_client.aclose()
    await close_pool()

    logger.info("AutoPilot DevOps Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
