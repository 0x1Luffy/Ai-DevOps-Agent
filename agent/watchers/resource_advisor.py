"""ResourceAdvisor — weekly right-sizing report for Kubernetes workloads."""

from __future__ import annotations

from typing import Any

import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


class ResourceAdvisor:
    """Generates weekly CPU/memory right-sizing recommendations."""

    async def generate_weekly_report(self) -> dict[str, Any]:
        """
        Analyse all tracked deployments for over/under-provisioned containers.

        Strategy:
        - Containers with limits set but no requests → Burstable QoS (risky)
        - Containers with no limits at all → risk of node-level resource starvation
        - Containers with memory limit < 2x memory request → risk of OOMKill under load
        - (Actual usage data would require Metrics-Server or Prometheus; this
          implementation uses the static Kubernetes spec only.)
        """
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config
        from kubernetes.client.rest import ApiException

        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        apps_v1 = k8s_client.AppsV1Api()

        report: dict[str, Any] = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "summary": {},
            "over_provisioned": [],
            "under_provisioned": [],
            "no_limits_set": [],
            "recommendations": [],
        }

        total_deployments = 0
        total_containers = 0

        for ns in settings.target_namespaces_list:
            try:
                deployments = apps_v1.list_namespaced_deployment(namespace=ns)
            except ApiException as exc:
                logger.warning("Cannot list deployments for advisor", namespace=ns, error=str(exc))
                continue

            for dep in deployments.items:
                total_deployments += 1
                containers = dep.spec.template.spec.containers or []
                for c in containers:
                    total_containers += 1
                    res = c.resources
                    dep_name = dep.metadata.name

                    if not res or (not res.limits and not res.requests):
                        report["no_limits_set"].append({
                            "namespace": ns,
                            "deployment": dep_name,
                            "container": c.name,
                            "recommendation": "Set both requests and limits to get Guaranteed QoS",
                        })
                        continue

                    limits = res.limits or {}
                    requests = res.requests or {}
                    cpu_limit = limits.get("cpu", "")
                    mem_limit = limits.get("memory", "")
                    cpu_req = requests.get("cpu", "")
                    mem_req = requests.get("memory", "")

                    # No requests set
                    if not cpu_req and not mem_req:
                        report["under_provisioned"].append({
                            "namespace": ns,
                            "deployment": dep_name,
                            "container": c.name,
                            "issue": "No resource requests set — scheduler cannot make optimal placement",
                            "recommendation": f"Set requests matching at least 50% of limits: cpu={cpu_limit} mem={mem_limit}",
                        })
                        continue

                    # Memory limit < 2x memory request
                    mem_limit_bytes = _parse_memory(mem_limit)
                    mem_req_bytes = _parse_memory(mem_req)
                    if mem_limit_bytes and mem_req_bytes and mem_limit_bytes < 2 * mem_req_bytes:
                        report["under_provisioned"].append({
                            "namespace": ns,
                            "deployment": dep_name,
                            "container": c.name,
                            "issue": f"Memory limit ({mem_limit}) is less than 2x request ({mem_req}) — OOMKill risk under burst load",
                            "recommendation": f"Increase memory limit to at least {_fmt_bytes(mem_req_bytes * 2)}",
                        })

                    # CPU limit = CPU request (identical) → over-provisioned for bursty apps
                    if cpu_limit and cpu_req and cpu_limit == cpu_req:
                        report["over_provisioned"].append({
                            "namespace": ns,
                            "deployment": dep_name,
                            "container": c.name,
                            "issue": f"CPU limit equals request ({cpu_req}) — prevents CPU bursting for Node.js event loop",
                            "recommendation": "Consider setting cpu_limit to 2-4x cpu_request for microservices",
                        })

        # Summary
        report["summary"] = {
            "total_deployments": total_deployments,
            "total_containers": total_containers,
            "no_limits_count": len(report["no_limits_set"]),
            "under_provisioned_count": len(report["under_provisioned"]),
            "over_provisioned_count": len(report["over_provisioned"]),
        }

        # Top recommendations
        if report["no_limits_set"]:
            report["recommendations"].append(
                f"Set resource limits on {len(report['no_limits_set'])} container(s) "
                "to prevent noisy-neighbour resource starvation."
            )
        if report["under_provisioned"]:
            report["recommendations"].append(
                f"Review {len(report['under_provisioned'])} under-provisioned container(s) "
                "to reduce OOMKill and scheduling failure risk."
            )
        if report["over_provisioned"]:
            report["recommendations"].append(
                f"{len(report['over_provisioned'])} container(s) have equal CPU request/limit "
                "— consider allowing CPU bursting for latency-sensitive workloads."
            )

        logger.info("Weekly resource right-sizing report generated", summary=report["summary"])

        # Send to Slack
        await self._post_report_to_slack(report)
        return report

    async def _post_report_to_slack(self, report: dict[str, Any]) -> None:
        """Post report summary to Slack alert channel."""
        try:
            from integrations.slack import SlackIntegration
            slack = SlackIntegration()
            summary = report["summary"]
            lines = [
                "*:chart_with_upwards_trend: Weekly Resource Right-Sizing Report*",
                f"Deployments analysed: *{summary['total_deployments']}* "
                f"({summary['total_containers']} containers)",
                f":warning: No limits set: *{summary['no_limits_count']}*",
                f":arrow_down: Under-provisioned: *{summary['under_provisioned_count']}*",
                f":arrow_up: Over-provisioned: *{summary['over_provisioned_count']}*",
            ]
            if report["recommendations"]:
                lines.append("\n*Recommendations:*")
                for rec in report["recommendations"]:
                    lines.append(f"• {rec}")
            slack.client.chat_postMessage(
                channel=settings.SLACK_ALERT_CHANNEL,
                text="\n".join(lines),
            )
        except Exception as exc:
            logger.warning("Failed to post right-sizing report to Slack", error=str(exc))


def _parse_memory(value: str) -> int:
    """Parse Kubernetes memory string to bytes."""
    if not value:
        return 0
    value = value.strip()
    multipliers = {
        "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3,
        "k": 1000, "M": 1000 ** 2, "G": 1000 ** 3,
    }
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return int(float(value[:-len(suffix)]) * mult)
            except ValueError:
                return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _fmt_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    if n >= 1024 ** 3:
        return f"{n // (1024 ** 3)}Gi"
    if n >= 1024 ** 2:
        return f"{n // (1024 ** 2)}Mi"
    if n >= 1024:
        return f"{n // 1024}Ki"
    return f"{n}"
