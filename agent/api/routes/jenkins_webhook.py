"""Jenkins webhook receiver."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from config.settings import settings
from integrations.jenkins import JenkinsIntegration

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])

_jenkins = JenkinsIntegration()


@router.post("/webhooks/jenkins")
async def jenkins_webhook(
    request: Request,
    x_jenkins_signature: str | None = Header(default=None, alias="X-Jenkins-Signature"),
    x_jenkins_signature_256: str | None = Header(default=None, alias="X-Jenkins-Signature-256"),
) -> dict[str, Any]:
    """Receive and process Jenkins build event webhooks."""
    body = await request.body()

    # Validate HMAC signature when webhook secret is configured
    if settings.JENKINS_WEBHOOK_SECRET:
        secret = settings.JENKINS_WEBHOOK_SECRET.encode()
        if x_jenkins_signature_256:
            expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(x_jenkins_signature_256, expected):
                logger.warning("Jenkins webhook signature mismatch (sha256)")
                raise HTTPException(status_code=403, detail="Invalid webhook signature")
        elif x_jenkins_signature:
            expected = "sha1=" + hmac.new(secret, body, hashlib.sha1).hexdigest()
            if not hmac.compare_digest(x_jenkins_signature, expected):
                logger.warning("Jenkins webhook signature mismatch (sha1)")
                raise HTTPException(status_code=403, detail="Invalid webhook signature")
        else:
            raise HTTPException(status_code=403, detail="Missing webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(
        "Jenkins webhook received",
        job=payload.get("name", "unknown"),
        build=payload.get("build", {}).get("number"),
    )

    result = await _jenkins.handle_webhook(payload)
    return {"status": "ok", **result}
