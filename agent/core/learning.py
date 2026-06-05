"""LearningEngine — tracks fix-pattern outcomes and generates right-sizing reports."""

from __future__ import annotations

from typing import Any

import structlog

from db.connection import get_pool
from db.repos.patterns import get_patterns, record_fix_attempt

logger = structlog.get_logger(__name__)


class LearningEngine:
    """Records fix outcomes and derives best-fix recommendations from historical data."""

    async def record_outcome(
        self,
        problem_pattern: str,
        fix_action: str,
        success: bool,
    ) -> None:
        """Persist a fix attempt result to the fix_patterns table."""
        pool = await get_pool()
        await record_fix_attempt(pool, problem_pattern, fix_action, success)
        logger.info(
            "Fix outcome recorded",
            pattern=problem_pattern,
            action=fix_action,
            success=success,
        )

    async def get_best_fix(self, problem_pattern: str) -> dict[str, Any] | None:
        """
        Return the fix action with the highest success rate for *problem_pattern*.

        Returns None if no patterns exist for this problem.
        """
        pool = await get_pool()
        patterns = await get_patterns(pool)

        candidates = [p for p in patterns if p["problem_pattern"] == problem_pattern]
        if not candidates:
            return None

        # Sort by success_rate desc, then success_count desc for tie-break
        best = sorted(
            candidates,
            key=lambda p: (float(p.get("success_rate", 0)), p.get("success_count", 0)),
            reverse=True,
        )[0]

        logger.debug(
            "Best fix found",
            pattern=problem_pattern,
            action=best["fix_action"],
            success_rate=best.get("success_rate"),
        )
        return best

    async def generate_weekly_report(self) -> dict[str, Any]:
        """
        Generate a weekly resource right-sizing report.

        Queries the cluster for CPU/memory usage vs. configured limits and
        returns a dict of recommendations.

        Note: Actual metric scraping is intentionally kept lightweight here —
        the report gathers data available in Kubernetes API without requiring
        Prometheus/Metrics-Server to be healthy.
        """
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
        from kubernetes.client.rest import ApiException
        from config.settings import settings

        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        apps_v1 = k8s_client.AppsV1Api()
        report: dict[str, Any] = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "over_provisioned": [],
            "under_provisioned": [],
            "no_limits_set": [],
        }

        for ns in settings.target_namespaces_list:
            try:
                deployments = apps_v1.list_namespaced_deployment(namespace=ns)
            except ApiException:
                continue

            for dep in deployments.items:
                containers = dep.spec.template.spec.containers or []
                for c in containers:
                    res = c.resources
                    if not res:
                        report["no_limits_set"].append({
                            "deployment": dep.metadata.name,
                            "namespace": ns,
                            "container": c.name,
                        })
                        continue

                    limits = res.limits or {}
                    requests = res.requests or {}

                    cpu_limit = limits.get("cpu", "")
                    mem_limit = limits.get("memory", "")
                    cpu_req = requests.get("cpu", "")
                    mem_req = requests.get("memory", "")

                    # Flag containers with limits set but no requests (poor QoS)
                    if (cpu_limit or mem_limit) and not (cpu_req and mem_req):
                        report["under_provisioned"].append({
                            "deployment": dep.metadata.name,
                            "namespace": ns,
                            "container": c.name,
                            "issue": "Limits set but requests missing — Burstable QoS class",
                            "cpu_limit": cpu_limit,
                            "memory_limit": mem_limit,
                        })

        logger.info(
            "Weekly right-sizing report generated",
            over_provisioned=len(report["over_provisioned"]),
            under_provisioned=len(report["under_provisioned"]),
            no_limits_set=len(report["no_limits_set"]),
        )
        return report
