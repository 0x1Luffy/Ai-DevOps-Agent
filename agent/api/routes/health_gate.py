"""Health gate endpoint — scored cluster health for CI/CD pre-deploy checks."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException

from config.settings import settings
from db.connection import get_pool

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/cluster/health-gate")
async def cluster_health_gate(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """
    Compute and return cluster health score for CI/CD pipeline gating.

    Score breakdown:
      - Nodes (40 pts)
      - Pod health (30 pts)
      - PVC health (15 pts)
      - Recent incidents (15 pts)
    """
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    pool = await get_pool()
    checks: dict[str, Any] = {}
    total_score = 0

    # ------------------------------------------------------------------
    # Nodes (40 pts)
    # ------------------------------------------------------------------
    node_score = 40
    node_issues: list[str] = []
    try:
        from kubernetes import client as k8s_client, config as k8s_config
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        core_v1 = k8s_client.CoreV1Api()
        import asyncio
        nodes = await asyncio.get_event_loop().run_in_executor(None, core_v1.list_node)

        total_nodes = len(nodes.items)
        not_ready_nodes = 0
        pressure_nodes = 0

        for node in nodes.items:
            for cond in (node.status.conditions or []):
                if cond.type == "Ready" and cond.status != "True":
                    not_ready_nodes += 1
                if cond.type in ("MemoryPressure", "DiskPressure", "PIDPressure") and cond.status == "True":
                    pressure_nodes += 1

        if total_nodes > 0:
            node_health_pct = (total_nodes - not_ready_nodes) / total_nodes
            node_score = int(40 * node_health_pct)
            if pressure_nodes > 0:
                node_score = max(0, node_score - pressure_nodes * 5)

        if not_ready_nodes:
            node_issues.append(f"{not_ready_nodes}/{total_nodes} node(s) NotReady")
        if pressure_nodes:
            node_issues.append(f"{pressure_nodes} node(s) under pressure")

    except Exception as exc:
        logger.warning("Health gate: node check failed", error=str(exc))
        node_score = 0
        node_issues.append(f"Cannot read nodes: {exc}")

    checks["nodes"] = {
        "score": node_score,
        "max_score": 40,
        "issues": node_issues,
    }
    total_score += node_score

    # ------------------------------------------------------------------
    # Pod health (30 pts)
    # ------------------------------------------------------------------
    pod_score = 30
    pod_issues: list[str] = []
    try:
        crash_total = 0
        pending_total = 0
        total_pods = 0

        for ns in settings.target_namespaces_list:
            try:
                pods = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda n=ns: core_v1.list_namespaced_pod(namespace=n),
                )
                for pod in pods.items:
                    total_pods += 1
                    if not pod.status or not pod.status.container_statuses:
                        if pod.status and pod.status.phase == "Pending":
                            pending_total += 1
                        continue
                    for cs in pod.status.container_statuses:
                        if cs.state and cs.state.waiting:
                            reason = cs.state.waiting.reason or ""
                            if reason in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"):
                                crash_total += 1
            except Exception:
                pass

        if total_pods > 0:
            bad_ratio = (crash_total + pending_total) / total_pods
            pod_score = max(0, int(30 * (1 - bad_ratio)))
        if crash_total:
            pod_issues.append(f"{crash_total} pod(s) in crash/image-pull state")
        if pending_total:
            pod_issues.append(f"{pending_total} pod(s) pending")

    except Exception as exc:
        logger.warning("Health gate: pod check failed", error=str(exc))
        pod_score = 0
        pod_issues.append(f"Cannot read pods: {exc}")

    checks["pod_health"] = {
        "score": pod_score,
        "max_score": 30,
        "issues": pod_issues,
    }
    total_score += pod_score

    # ------------------------------------------------------------------
    # PVC health (15 pts)
    # ------------------------------------------------------------------
    pvc_score = 15
    pvc_issues: list[str] = []
    try:
        lost_pvcs = 0
        pending_pvcs = 0

        for ns in settings.target_namespaces_list:
            try:
                pvcs = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda n=ns: core_v1.list_namespaced_persistent_volume_claim(namespace=n),
                )
                for pvc in pvcs.items:
                    phase = pvc.status.phase if pvc.status else ""
                    if phase == "Lost":
                        lost_pvcs += 1
                    elif phase == "Pending":
                        pending_pvcs += 1
            except Exception:
                pass

        if lost_pvcs:
            pvc_score -= lost_pvcs * 7
            pvc_issues.append(f"{lost_pvcs} PVC(s) in Lost state")
        if pending_pvcs:
            pvc_score -= pending_pvcs * 3
            pvc_issues.append(f"{pending_pvcs} PVC(s) pending")
        pvc_score = max(0, pvc_score)

    except Exception as exc:
        logger.warning("Health gate: PVC check failed", error=str(exc))
        pvc_score = 0
        pvc_issues.append(f"Cannot read PVCs: {exc}")

    checks["pvc_health"] = {
        "score": pvc_score,
        "max_score": 15,
        "issues": pvc_issues,
    }
    total_score += pvc_score

    # ------------------------------------------------------------------
    # Recent incidents (15 pts)
    # ------------------------------------------------------------------
    incident_score = 15
    incident_issues: list[str] = []
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE severity = 'CRITICAL') AS crit,
                    COUNT(*) FILTER (WHERE severity = 'HIGH')     AS high,
                    COUNT(*) FILTER (WHERE status NOT IN ('fixed','skipped')) AS open
                FROM incidents
                WHERE detected_at > $1
                """,
                since,
            )
        if row:
            crit = row["crit"] or 0
            high = row["high"] or 0
            open_count = row["open"] or 0
            incident_score -= crit * 8
            incident_score -= high * 3
            incident_score -= open_count * 1
            incident_score = max(0, incident_score)
            if crit:
                incident_issues.append(f"{crit} CRITICAL incident(s) in last hour")
            if high:
                incident_issues.append(f"{high} HIGH incident(s) in last hour")

    except Exception as exc:
        logger.warning("Health gate: incident check failed", error=str(exc))
        incident_score = 0
        incident_issues.append(f"Cannot read incidents: {exc}")

    checks["recent_incidents"] = {
        "score": incident_score,
        "max_score": 15,
        "issues": incident_issues,
    }
    total_score += incident_score

    # ------------------------------------------------------------------
    # Overall status
    # ------------------------------------------------------------------
    if total_score >= 90:
        status = "HEALTHY"
        recommendation = "Safe to deploy"
    elif total_score >= 70:
        status = "DEGRADED"
        recommendation = "Cluster degraded — review issues before deploying"
    else:
        status = "UNHEALTHY"
        recommendation = "Do NOT deploy — cluster is unhealthy"

    all_issues = (
        node_issues + pod_issues + pvc_issues + incident_issues
    )

    return {
        "status": status,
        "score": total_score,
        "max_score": 100,
        "recommendation": recommendation,
        "checks": checks,
        "issues": all_issues,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
