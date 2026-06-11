"""Human approval endpoints for pending fixes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config.settings import settings
from db.connection import get_pool
from db.repos.incidents import get_incident

router = APIRouter(tags=["approvals"])


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=1)


def _check_api_key(x_api_key: str | None) -> None:
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/fixes/{incident_id}/approve")
async def approve_fix(
    incident_id: str,
    payload: ApprovalRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, str]:
    _check_api_key(x_api_key)

    pool = await get_pool()
    incident = await get_incident(pool, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.get("status") != "needs_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Incident is not awaiting approval (current status: {incident.get('status')})",
        )

    fix_plan = incident.get("fix_plan") or []
    if isinstance(fix_plan, str):
        fix_plan = json.loads(fix_plan)

    from core.executor import FixExecutor
    executor = FixExecutor()
    await executor.execute_fix_plan(
        incident_id,
        fix_plan,
        approver_slack_id=payload.approver,
    )

    return {"status": "ok", "message": "Fix executed"}
