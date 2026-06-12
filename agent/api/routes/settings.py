"""Runtime settings endpoint for the dashboard."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config.settings import runtime_config, settings

router = APIRouter(tags=["settings"])


def _check_api_key(x_api_key: str | None) -> None:
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class AgentConfigUpdate(BaseModel):
    enableAutoFix: bool | None = None
    dryRun: bool | None = None
    driftAutoCorrect: bool | None = None
    confidenceThreshold: int | None = Field(default=None, ge=0, le=100)
    scanIntervalSeconds: int | None = Field(default=None, ge=5, le=3600)
    postFixVerifyDelaySeconds: int | None = Field(default=None, ge=5, le=3600)
    slackApprovalTimeoutMinutes: int | None = Field(default=None, ge=1, le=1440)
    targetNamespaces: list[str] | None = None
    llmProvider: Literal["anthropic", "openai"] | None = None
    claudeModel: str | None = None
    openaiModel: str | None = None


def _current_config() -> dict[str, Any]:
    return {
        "enableAutoFix": bool(runtime_config.get("ENABLE_AUTO_FIX", settings.ENABLE_AUTO_FIX)),
        "dryRun": bool(runtime_config.get("DRY_RUN", settings.DRY_RUN)),
        "driftAutoCorrect": bool(runtime_config.get("DRIFT_AUTO_CORRECT", settings.DRIFT_AUTO_CORRECT)),
        "confidenceThreshold": int(runtime_config.get("AI_CONFIDENCE_THRESHOLD", settings.AI_CONFIDENCE_THRESHOLD)),
        "scanIntervalSeconds": int(settings.SCAN_INTERVAL_SECONDS),
        "postFixVerifyDelaySeconds": int(settings.POST_FIX_VERIFY_DELAY_SECONDS),
        "slackApprovalTimeoutMinutes": int(settings.SLACK_APPROVAL_TIMEOUT_MINUTES),
        "targetNamespaces": settings.target_namespaces_list,
        "llmProvider": str(runtime_config.get("LLM_PROVIDER", settings.LLM_PROVIDER)),
        "claudeModel": str(runtime_config.get("CLAUDE_MODEL", settings.CLAUDE_MODEL)),
        "openaiModel": str(runtime_config.get("OPENAI_MODEL", settings.OPENAI_MODEL)),
    }


@router.get("/settings/config")
async def get_config(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    return _current_config()


@router.patch("/settings/config")
async def update_config(
    update: AgentConfigUpdate,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _check_api_key(x_api_key)

    if update.enableAutoFix is not None:
        runtime_config["ENABLE_AUTO_FIX"] = update.enableAutoFix
        settings.ENABLE_AUTO_FIX = update.enableAutoFix
    if update.dryRun is not None:
        runtime_config["DRY_RUN"] = update.dryRun
        settings.DRY_RUN = update.dryRun
    if update.driftAutoCorrect is not None:
        runtime_config["DRIFT_AUTO_CORRECT"] = update.driftAutoCorrect
        settings.DRIFT_AUTO_CORRECT = update.driftAutoCorrect
    if update.confidenceThreshold is not None:
        runtime_config["AI_CONFIDENCE_THRESHOLD"] = update.confidenceThreshold
        settings.AI_CONFIDENCE_THRESHOLD = update.confidenceThreshold
    if update.scanIntervalSeconds is not None:
        settings.SCAN_INTERVAL_SECONDS = update.scanIntervalSeconds
    if update.postFixVerifyDelaySeconds is not None:
        settings.POST_FIX_VERIFY_DELAY_SECONDS = update.postFixVerifyDelaySeconds
    if update.slackApprovalTimeoutMinutes is not None:
        settings.SLACK_APPROVAL_TIMEOUT_MINUTES = update.slackApprovalTimeoutMinutes
    if update.targetNamespaces is not None:
        namespaces = [ns.strip() for ns in update.targetNamespaces if ns.strip()]
        settings.TARGET_NAMESPACES = ",".join(namespaces)
    if update.llmProvider is not None:
        if update.llmProvider == "anthropic" and not settings.ANTHROPIC_API_KEY:
            raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY is not configured")
        if update.llmProvider == "openai" and not settings.OPENAI_API_KEY:
            raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not configured")
        runtime_config["LLM_PROVIDER"] = update.llmProvider
        settings.LLM_PROVIDER = update.llmProvider
    if update.claudeModel is not None:
        runtime_config["CLAUDE_MODEL"] = update.claudeModel
        settings.CLAUDE_MODEL = update.claudeModel
    if update.openaiModel is not None:
        runtime_config["OPENAI_MODEL"] = update.openaiModel
        settings.OPENAI_MODEL = update.openaiModel

    return _current_config()
