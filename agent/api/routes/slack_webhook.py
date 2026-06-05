"""Slack Events API webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from config.settings import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])


def _verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify the X-Slack-Signature header using the signing secret."""
    if not settings.SLACK_SIGNING_SECRET:
        return True  # Skip verification if no secret configured

    # Reject stale requests (>5 min old)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@router.post("/webhooks/slack")
async def slack_webhook(
    request: Request,
    x_slack_signature: str | None = Header(default=None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(default=None, alias="X-Slack-Request-Timestamp"),
) -> dict[str, Any]:
    """Handle incoming Slack Events API payloads."""
    body = await request.body()

    # Signature verification
    if settings.SLACK_SIGNING_SECRET:
        if not x_slack_signature or not x_slack_request_timestamp:
            raise HTTPException(status_code=403, detail="Missing Slack signature headers")
        if not _verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
            logger.warning("Slack signature verification failed")
            raise HTTPException(status_code=403, detail="Invalid Slack signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # URL verification challenge (required when first connecting app)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # Slack events are handled by the Bolt app running in the background thread.
    # This endpoint only needs to return 200 OK quickly to avoid Slack retries.
    logger.info(
        "Slack event received",
        event_type=payload.get("event", {}).get("type"),
        team=payload.get("team_id"),
    )
    return {"status": "ok"}
