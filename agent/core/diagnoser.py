"""DiagnoserEngine — uses Claude to analyse Kubernetes incidents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import structlog
from pydantic import BaseModel, Field

from config.prompts.k8s_diagnosis import K8S_SYSTEM_PROMPT
from config.settings import runtime_config, settings
from core.llm import get_llm_client
from db.connection import get_pool
from db.repos.incidents import create_incident, update_incident_status

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class IncidentEvent(BaseModel):
    """Validated incident event consumed from the Redis queue."""

    resource_type: str
    resource_name: str
    namespace: str
    problem_type: str
    severity: str = "MEDIUM"
    context: dict[str, Any] = Field(default_factory=dict)
    detected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class FixStep(BaseModel):
    """A single step in the auto-fix plan."""

    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    kubectl_equivalent: str = ""


class DiagnosisResult(BaseModel):
    """Parsed diagnosis from Claude."""

    incident_id: str
    root_cause: str
    severity: str
    auto_fixable: bool
    not_auto_fixable_reason: str = ""
    confidence: int
    fix_plan: list[FixStep] = Field(default_factory=list)
    prevention_tip: str = ""
    estimated_recovery: str = ""
    related_resources: list[str] = Field(default_factory=list)
    cascade_risk: str = ""
    node_js_specific: str = ""
    claude_raw: str = ""


# ---------------------------------------------------------------------------
# Auto-fix gate rules
# ---------------------------------------------------------------------------

_KUBE_SYSTEM_SAFE = {"coredns", "metrics-server"}

VALID_FIX_ACTIONS = {
    "patch_deployment", "rollout_undo", "delete_pod", "patch_service",
    "scale_hpa", "restart_daemonset", "patch_resource_limits", "cordon_node",
    "evict_pods_from_node", "restart_metrics_server", "add_image_to_blacklist",
    "delete_evicted_pods", "force_delete_pod", "patch_probe_config", "restart_coredns",
}


def _auto_fix_gate(incident: IncidentEvent, diagnosis: dict[str, Any]) -> tuple[bool, str]:
    """
    Evaluate all 7 hard rules.  Returns (can_auto_fix, reason_if_not).
    """
    namespace = incident.namespace
    resource_type = incident.resource_type
    resource_name = incident.resource_name
    severity = diagnosis.get("severity", "MEDIUM")
    confidence = diagnosis.get("confidence", 0)
    threshold = runtime_config.get("AI_CONFIDENCE_THRESHOLD", settings.AI_CONFIDENCE_THRESHOLD)

    # Rule 1 — CRITICAL severity always needs approval
    if severity == "CRITICAL":
        return False, "CRITICAL severity requires human approval"

    # Rule 2 — kube-system namespace (except coredns/metrics-server)
    if namespace == "kube-system":
        safe = any(s in resource_name.lower() for s in _KUBE_SYSTEM_SAFE)
        if not safe:
            return False, "kube-system resources require human approval (except coredns/metrics-server)"

    # Rule 3 — Never touch PVC/Secret/RBAC
    if resource_type in ("pvc", "secret", "clusterrole", "clusterrolebinding", "role", "rolebinding"):
        return False, f"Modifications to {resource_type} require human approval"

    # Rule 4 — Confidence below threshold
    if confidence < threshold:
        return False, f"AI confidence {confidence}% below threshold {threshold}%"

    # Rule 5 — Fix plan contains disallowed actions
    fix_plan = diagnosis.get("fixPlan", [])
    for step in fix_plan:
        action = step.get("action", "")
        if action not in VALID_FIX_ACTIONS:
            return False, f"Fix action '{action}' is not in the approved action list"

    # Rule 6 — NetworkPolicy / PDB / quota increase actions disallowed
    disallowed_problem_types = {
        "ResourceQuotaExceeded", "PVCLost", "PVCPending",
    }
    if incident.problem_type in disallowed_problem_types:
        return False, f"Problem type {incident.problem_type} requires human intervention"

    # Rule 7 — Global auto-fix kill switch
    if not runtime_config.get("ENABLE_AUTO_FIX", settings.ENABLE_AUTO_FIX):
        return False, "ENABLE_AUTO_FIX is disabled"

    # Claude said not auto-fixable
    if not diagnosis.get("autoFixable", False):
        reason = diagnosis.get("notAutoFixableReason", "Claude determined this is not auto-fixable")
        return False, reason

    return True, ""


# ---------------------------------------------------------------------------
# DiagnoserEngine
# ---------------------------------------------------------------------------


class DiagnoserEngine:
    """Async engine that sends incident context to Claude and parses the diagnosis."""

    def __init__(self) -> None:
        self._llm = get_llm_client()
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def diagnose(self, incident: IncidentEvent) -> DiagnosisResult:
        """
        Send incident context to Claude, parse diagnosis, apply auto-fix gate,
        persist to DB, and publish to Redis pub/sub.
        """
        pool = await get_pool()

        # Persist incident as 'diagnosing'
        incident_id = await create_incident(
            pool,
            {
                "resource_type": incident.resource_type,
                "resource_name": incident.resource_name,
                "namespace": incident.namespace,
                "problem_type": incident.problem_type,
                "severity": incident.severity,
                "status": "diagnosing",
                "full_context": incident.context,
            },
        )

        prompt = self._build_prompt(incident)
        logger.info(
            "Sending incident to Claude",
            incident_id=incident_id,
            resource=incident.resource_name,
            problem=incident.problem_type,
        )

        raw_response = ""
        diagnosis_dict: dict[str, Any] = {}

        # First attempt
        try:
            raw_response = await self._call_llm(prompt)
            diagnosis_dict = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed on first attempt, retrying with repair prompt")
            try:
                repair_prompt = (
                    f"The following is a broken JSON response. "
                    f"Fix it and return ONLY valid JSON:\n\n{raw_response}"
                )
                raw_response = await self._call_llm(repair_prompt)
                diagnosis_dict = json.loads(raw_response)
            except Exception as exc:
                logger.error("Failed to parse AI response after retry", error=str(exc))
                diagnosis_dict = {
                    "rootCause": "Unable to parse AI diagnosis",
                    "severity": incident.severity,
                    "autoFixable": False,
                    "notAutoFixableReason": "Diagnosis parsing failed",
                    "confidence": 0,
                    "fixPlan": [],
                    "preventionTip": "",
                    "estimatedRecovery": "unknown",
                    "relatedResources": [],
                    "cascadeRisk": "",
                    "nodeJsSpecific": "",
                }
        except Exception as exc:
            logger.error("LLM API call failed", error=str(exc))
            raise

        # Apply auto-fix gate
        can_auto_fix, gate_reason = _auto_fix_gate(incident, diagnosis_dict)

        # Parse fix plan
        fix_plan_raw = diagnosis_dict.get("fixPlan", [])
        fix_plan = [
            FixStep(
                action=step.get("action", ""),
                params=step.get("params", {}),
                description=step.get("description", ""),
                kubectl_equivalent=step.get("kubectl_equivalent", ""),
            )
            for step in fix_plan_raw
            if isinstance(step, dict)
        ]

        result = DiagnosisResult(
            incident_id=incident_id,
            root_cause=diagnosis_dict.get("rootCause", ""),
            severity=diagnosis_dict.get("severity", incident.severity),
            auto_fixable=can_auto_fix,
            not_auto_fixable_reason=gate_reason or diagnosis_dict.get("notAutoFixableReason", ""),
            confidence=diagnosis_dict.get("confidence", 0),
            fix_plan=fix_plan,
            prevention_tip=diagnosis_dict.get("preventionTip", ""),
            estimated_recovery=diagnosis_dict.get("estimatedRecovery", ""),
            related_resources=diagnosis_dict.get("relatedResources", []),
            cascade_risk=diagnosis_dict.get("cascadeRisk", ""),
            node_js_specific=diagnosis_dict.get("nodeJsSpecific", ""),
            claude_raw=raw_response,
        )

        # Update incident in DB
        new_status = "open" if can_auto_fix else "needs_approval"
        await update_incident_status(
            pool,
            incident_id,
            new_status,
            root_cause=result.root_cause,
            confidence=result.confidence,
            auto_fixable=result.auto_fixable,
            fix_plan=[s.model_dump() for s in result.fix_plan],
            prevention_tip=result.prevention_tip,
            estimated_recovery=result.estimated_recovery,
            related_resources=result.related_resources,
            claude_prompt=prompt,
            claude_response=raw_response,
        )

        # Publish to Redis
        redis_client = await self._get_redis()
        event_payload = json.dumps({
            "event": "diagnosis_complete",
            "incident_id": incident_id,
            "resource": incident.resource_name,
            "namespace": incident.namespace,
            "severity": result.severity,
            "auto_fixable": result.auto_fixable,
            "confidence": result.confidence,
        })
        await redis_client.publish("autopilot:events", event_payload)

        logger.info(
            "Diagnosis complete",
            incident_id=incident_id,
            severity=result.severity,
            confidence=result.confidence,
            auto_fixable=result.auto_fixable,
        )
        return result

    async def _call_llm(self, prompt: str) -> str:
        """Send prompt to the active LLM provider and return the raw text response."""
        return await self._llm.complete(
            system=K8S_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=2048,
            json_mode=True,
        )

    @staticmethod
    def _build_prompt(incident: IncidentEvent) -> str:
        """Build the user prompt from the incident data."""
        ctx = incident.context
        lines = [
            f"INCIDENT REPORT",
            f"===============",
            f"Resource Type  : {incident.resource_type}",
            f"Resource Name  : {incident.resource_name}",
            f"Namespace      : {incident.namespace}",
            f"Problem Type   : {incident.problem_type}",
            f"Initial Severity: {incident.severity}",
            f"Detected At    : {incident.detected_at}",
            "",
        ]

        if ctx.get("logs"):
            lines.append("--- Container Logs (last 100 lines) ---")
            lines.append(str(ctx["logs"])[:3000])
            lines.append("")

        if ctx.get("previous_logs"):
            lines.append("--- Previous Container Logs ---")
            lines.append(str(ctx["previous_logs"])[:1500])
            lines.append("")

        if ctx.get("events"):
            lines.append("--- Kubernetes Events ---")
            for ev in ctx["events"]:
                lines.append(
                    f"[{ev.get('type')}] {ev.get('reason')}: {ev.get('message')} (count={ev.get('count')})"
                )
            lines.append("")

        # Any extra context fields
        for key, value in ctx.items():
            if key not in ("logs", "previous_logs", "events"):
                lines.append(f"{key}: {value}")

        return "\n".join(lines)
