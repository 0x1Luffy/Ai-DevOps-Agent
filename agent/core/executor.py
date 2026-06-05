"""FixExecutor — executes approved fix actions against the Kubernetes cluster."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from config.settings import runtime_config, settings
from db.connection import get_pool
from db.repos.fixes import create_fix_execution, update_fix_execution
from db.repos.incidents import update_incident_status

logger = structlog.get_logger(__name__)


@dataclass
class FixResult:
    """Result of a fix action execution."""

    success: bool
    fix_id: str = ""
    action: str = ""
    error: str = ""
    duration_ms: int = 0
    kubectl_commands: list[str] = field(default_factory=list)


class FixExecutor:
    """Executes fix actions derived from Claude diagnosis results."""

    def __init__(self) -> None:
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        self.core_v1 = k8s_client.CoreV1Api()
        self.apps_v1 = k8s_client.AppsV1Api()
        self.autoscaling_v1 = k8s_client.AutoscalingV1Api()
        self._image_blacklist: set[str] = set()
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute_fix_plan(
        self,
        incident_id: str,
        fix_plan: list[dict[str, Any]],
        approver_slack_id: str | None = None,
    ) -> list[FixResult]:
        """Execute all steps of a fix plan sequentially."""
        results: list[FixResult] = []
        pool = await get_pool()

        await update_incident_status(pool, incident_id, "fixing")

        for step in fix_plan:
            action = step.get("action", "")
            params = step.get("params", {})
            description = step.get("description", "")
            kubectl_cmd = step.get("kubectl_equivalent", "")

            fix_id = await create_fix_execution(
                pool,
                {
                    "incident_id": incident_id,
                    "fix_action": action,
                    "fix_params": params,
                    "fix_description": description,
                    "kubectl_commands": [kubectl_cmd] if kubectl_cmd else [],
                    "executed_by": "auto" if not approver_slack_id else "approved",
                    "approver_slack_id": approver_slack_id,
                    "result": None,
                    "verification_status": "pending",
                },
            )

            result = await self._dispatch(action, params, fix_id, incident_id)
            results.append(result)

            # Publish event
            redis_client = await self._get_redis()
            await redis_client.publish(
                "autopilot:events",
                json.dumps({
                    "event": "fix_executed",
                    "incident_id": incident_id,
                    "fix_id": fix_id,
                    "action": action,
                    "success": result.success,
                }),
            )

            if not result.success:
                logger.warning(
                    "Fix step failed, stopping plan",
                    action=action,
                    error=result.error,
                    incident_id=incident_id,
                )
                break

        # Determine final incident status
        if all(r.success for r in results):
            await update_incident_status(pool, incident_id, "fixed",
                                         resolved_at=datetime.now(timezone.utc))
            # Schedule verification
            asyncio.get_event_loop().call_later(
                settings.POST_FIX_VERIFY_DELAY_SECONDS,
                lambda: asyncio.ensure_future(self._schedule_verify(incident_id, results)),
            )
        elif any(r.success for r in results):
            await update_incident_status(pool, incident_id, "fixing")
        else:
            await update_incident_status(pool, incident_id, "still_broken")

        return results

    async def _dispatch(
        self,
        action: str,
        params: dict[str, Any],
        fix_id: str,
        incident_id: str,
    ) -> FixResult:
        """Route an action string to the correct handler method."""
        dispatch_map = {
            "patch_deployment": self.patch_deployment,
            "rollout_undo": self.rollout_undo,
            "delete_pod": self.delete_pod,
            "force_delete_pod": self.force_delete_pod,
            "patch_service": self.patch_service,
            "scale_hpa": self.scale_hpa,
            "restart_daemonset": self.restart_deployment,  # reuse restart
            "patch_resource_limits": self.patch_resource_limits,
            "cordon_node": self.cordon_node,
            "evict_pods_from_node": self.evict_pods_from_node,
            "restart_metrics_server": self.restart_metrics_server,
            "add_image_to_blacklist": self.add_to_image_blacklist,
            "delete_evicted_pods": self.delete_evicted_pods,
            "patch_probe_config": self.patch_probe_config,
            "restart_coredns": self.restart_coredns,
        }
        handler = dispatch_map.get(action)
        if handler is None:
            msg = f"Unknown fix action: {action}"
            logger.warning(msg, incident_id=incident_id)
            pool = await get_pool()
            await update_fix_execution(pool, fix_id, result="skipped", error_message=msg)
            return FixResult(success=False, fix_id=fix_id, action=action, error=msg)

        start_ms = int(time.monotonic() * 1000)
        try:
            result = await handler(params, fix_id)
            result.duration_ms = int(time.monotonic() * 1000) - start_ms
            pool = await get_pool()
            await update_fix_execution(
                pool,
                fix_id,
                result="success" if result.success else "failed",
                error_message=result.error or None,
                execution_duration_ms=result.duration_ms,
            )
            return result
        except Exception as exc:
            duration_ms = int(time.monotonic() * 1000) - start_ms
            logger.exception("Fix action raised exception", action=action, error=str(exc))
            pool = await get_pool()
            await update_fix_execution(
                pool,
                fix_id,
                result="failed",
                error_message=str(exc),
                execution_duration_ms=duration_ms,
            )
            return FixResult(success=False, fix_id=fix_id, action=action, error=str(exc), duration_ms=duration_ms)

    async def _schedule_verify(self, incident_id: str, results: list[FixResult]) -> None:
        """Invoked after POST_FIX_VERIFY_DELAY_SECONDS to trigger feedback loop."""
        from core.feedback_loop import FeedbackLoop  # local import to avoid circular
        loop = FeedbackLoop()
        for result in results:
            if result.fix_id:
                await loop.verify_fix(incident_id=incident_id, fix_id=result.fix_id)

    # ------------------------------------------------------------------
    # Fix methods
    # ------------------------------------------------------------------

    async def patch_deployment(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Apply a JSON patch to a Deployment."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] patch_deployment skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="patch_deployment")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        patch = params.get("patch", {})

        cmd = f"kubectl patch deployment {name} -n {namespace} --patch '{json.dumps(patch)}'"
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=patch
                ),
            )
            logger.info("Deployment patched", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="patch_deployment", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="patch_deployment",
                             error=str(exc), kubectl_commands=[cmd])

    async def rollout_undo(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Roll back a Deployment to the previous revision."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] rollout_undo skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="rollout_undo")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        cmd = f"kubectl rollout undo deployment/{name} -n {namespace}"

        try:
            loop = asyncio.get_event_loop()
            rollback_body = {
                "spec": {
                    "rollbackTo": {"revision": params.get("revision", 0)}
                }
            }
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=rollback_body
                ),
            )
            logger.info("Rollout undo triggered", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="rollout_undo", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="rollout_undo",
                             error=str(exc), kubectl_commands=[cmd])

    async def delete_pod(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Delete a pod (Kubernetes will recreate it via the ReplicaSet)."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] delete_pod skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="delete_pod")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        cmd = f"kubectl delete pod {name} -n {namespace}"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.core_v1.delete_namespaced_pod(name=name, namespace=namespace),
            )
            logger.info("Pod deleted", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="delete_pod", kubectl_commands=[cmd])
        except ApiException as exc:
            if exc.status == 404:
                return FixResult(success=True, fix_id=fix_id, action="delete_pod",
                                 kubectl_commands=[cmd])  # idempotent
            return FixResult(success=False, fix_id=fix_id, action="delete_pod",
                             error=str(exc), kubectl_commands=[cmd])

    async def force_delete_pod(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Force-delete a stuck/terminating pod."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] force_delete_pod skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="force_delete_pod")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        cmd = f"kubectl delete pod {name} -n {namespace} --grace-period=0 --force"

        try:
            loop = asyncio.get_event_loop()
            grace_period = 0
            await loop.run_in_executor(
                None,
                lambda: self.core_v1.delete_namespaced_pod(
                    name=name,
                    namespace=namespace,
                    grace_period_seconds=grace_period,
                    body=k8s_client.V1DeleteOptions(grace_period_seconds=0),
                ),
            )
            logger.info("Pod force-deleted", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="force_delete_pod", kubectl_commands=[cmd])
        except ApiException as exc:
            if exc.status == 404:
                return FixResult(success=True, fix_id=fix_id, action="force_delete_pod",
                                 kubectl_commands=[cmd])
            return FixResult(success=False, fix_id=fix_id, action="force_delete_pod",
                             error=str(exc), kubectl_commands=[cmd])

    async def patch_service(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Apply a patch to a Service resource."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] patch_service skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="patch_service")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        patch = params.get("patch", {})
        cmd = f"kubectl patch service {name} -n {namespace} --patch '{json.dumps(patch)}'"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.core_v1.patch_namespaced_service(
                    name=name, namespace=namespace, body=patch
                ),
            )
            logger.info("Service patched", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="patch_service", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="patch_service",
                             error=str(exc), kubectl_commands=[cmd])

    async def scale_hpa(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Adjust the min/max replicas of an HPA."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] scale_hpa skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="scale_hpa")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        min_replicas = params.get("min_replicas")
        max_replicas = params.get("max_replicas")

        patch: dict[str, Any] = {"spec": {}}
        if min_replicas is not None:
            patch["spec"]["minReplicas"] = int(min_replicas)
        if max_replicas is not None:
            patch["spec"]["maxReplicas"] = int(max_replicas)

        cmd = f"kubectl patch hpa {name} -n {namespace} --patch '{json.dumps(patch)}'"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.autoscaling_v1.patch_namespaced_horizontal_pod_autoscaler(
                    name=name, namespace=namespace, body=patch
                ),
            )
            logger.info("HPA scaled", name=name, namespace=namespace, patch=patch)
            return FixResult(success=True, fix_id=fix_id, action="scale_hpa", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="scale_hpa",
                             error=str(exc), kubectl_commands=[cmd])

    async def patch_resource_limits(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Patch resource requests/limits on a deployment container."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] patch_resource_limits skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="patch_resource_limits")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        container = params.get("container", "")
        requests = params.get("requests", {})
        limits = params.get("limits", {})

        # Build strategic merge patch
        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container,
                                "resources": {
                                    "requests": requests,
                                    "limits": limits,
                                },
                            }
                        ]
                    }
                }
            }
        }
        cmd = f"kubectl patch deployment {name} -n {namespace} --patch '{json.dumps(patch)}'"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=patch
                ),
            )
            logger.info("Resource limits patched", name=name, namespace=namespace, container=container)
            return FixResult(success=True, fix_id=fix_id, action="patch_resource_limits", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="patch_resource_limits",
                             error=str(exc), kubectl_commands=[cmd])

    async def cordon_node(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Cordon a node to prevent new pods from being scheduled."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] cordon_node skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="cordon_node")

        node_name = params.get("name", "")
        cmd = f"kubectl cordon {node_name}"

        try:
            loop = asyncio.get_event_loop()
            patch = {"spec": {"unschedulable": True}}
            await loop.run_in_executor(
                None,
                lambda: self.core_v1.patch_node(name=node_name, body=patch),
            )
            logger.info("Node cordoned", node=node_name)
            return FixResult(success=True, fix_id=fix_id, action="cordon_node", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="cordon_node",
                             error=str(exc), kubectl_commands=[cmd])

    async def evict_pods_from_node(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Evict all non-DaemonSet pods from a node."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] evict_pods_from_node skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="evict_pods_from_node")

        node_name = params.get("name", "")
        namespace = params.get("namespace")
        cmd = f"kubectl drain {node_name} --ignore-daemonsets --delete-emptydir-data"

        try:
            loop = asyncio.get_event_loop()
            # List all pods on the node
            field_selector = f"spec.nodeName={node_name}"
            if namespace:
                pods = self.core_v1.list_namespaced_pod(
                    namespace=namespace, field_selector=field_selector
                )
            else:
                pods = self.core_v1.list_pod_for_all_namespaces(
                    field_selector=field_selector
                )

            eviction_body = k8s_client.V1Eviction(
                metadata=k8s_client.V1ObjectMeta()
            )
            errors = []
            for pod in pods.items:
                # Skip DaemonSet-managed pods
                owner_refs = pod.metadata.owner_references or []
                if any(ref.kind == "DaemonSet" for ref in owner_refs):
                    continue
                try:
                    eviction_body.metadata.name = pod.metadata.name
                    eviction_body.metadata.namespace = pod.metadata.namespace
                    await loop.run_in_executor(
                        None,
                        lambda p=pod, e=eviction_body: self.core_v1.create_namespaced_pod_eviction(
                            name=p.metadata.name,
                            namespace=p.metadata.namespace,
                            body=e,
                        ),
                    )
                except ApiException as exc:
                    errors.append(str(exc))

            if errors:
                return FixResult(success=False, fix_id=fix_id, action="evict_pods_from_node",
                                 error="; ".join(errors[:3]), kubectl_commands=[cmd])
            logger.info("Pods evicted from node", node=node_name)
            return FixResult(success=True, fix_id=fix_id, action="evict_pods_from_node", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="evict_pods_from_node",
                             error=str(exc), kubectl_commands=[cmd])

    async def restart_deployment(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Restart a Deployment by patching the pod template annotation."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] restart_deployment skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="restart_daemonset")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        cmd = f"kubectl rollout restart deployment/{name} -n {namespace}"

        restart_patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "autopilot.io/restartedAt": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            }
        }
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=restart_patch
                ),
            )
            logger.info("Deployment restarted", name=name, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="restart_daemonset", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="restart_daemonset",
                             error=str(exc), kubectl_commands=[cmd])

    async def add_to_image_blacklist(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Add a broken image tag to the in-memory blacklist."""
        image = params.get("image", "")
        if image:
            self._image_blacklist.add(image)
            logger.warning("Image added to blacklist", image=image)
        return FixResult(success=True, fix_id=fix_id, action="add_image_to_blacklist")

    async def restart_metrics_server(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Restart the metrics-server pods in kube-system."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] restart_metrics_server skipped")
            return FixResult(success=True, fix_id=fix_id, action="restart_metrics_server")

        namespace = "kube-system"
        label_selector = "k8s-app=metrics-server"
        cmd = f"kubectl rollout restart deployment/metrics-server -n {namespace}"

        try:
            loop = asyncio.get_event_loop()
            pods = await loop.run_in_executor(
                None,
                lambda: self.core_v1.list_namespaced_pod(
                    namespace=namespace, label_selector=label_selector
                ),
            )
            for pod in pods.items:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda p=pod: self.core_v1.delete_namespaced_pod(
                            name=p.metadata.name, namespace=namespace
                        ),
                    )
                except ApiException:
                    pass
            logger.info("metrics-server pods restarted")
            return FixResult(success=True, fix_id=fix_id, action="restart_metrics_server",
                             kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="restart_metrics_server",
                             error=str(exc), kubectl_commands=[cmd])

    async def delete_evicted_pods(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Delete all Evicted pods in a namespace to free scheduler capacity."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] delete_evicted_pods skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="delete_evicted_pods")

        namespace = params.get("namespace", "default")
        cmd = f"kubectl delete pods --field-selector=status.phase=Failed -n {namespace}"

        try:
            loop = asyncio.get_event_loop()
            pods = await loop.run_in_executor(
                None,
                lambda: self.core_v1.list_namespaced_pod(
                    namespace=namespace,
                    field_selector="status.phase=Failed",
                ),
            )
            deleted = 0
            for pod in pods.items:
                reason = pod.status.reason if pod.status else ""
                if reason == "Evicted":
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda p=pod: self.core_v1.delete_namespaced_pod(
                                name=p.metadata.name, namespace=namespace
                            ),
                        )
                        deleted += 1
                    except ApiException:
                        pass
            logger.info("Evicted pods deleted", count=deleted, namespace=namespace)
            return FixResult(success=True, fix_id=fix_id, action="delete_evicted_pods",
                             kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="delete_evicted_pods",
                             error=str(exc), kubectl_commands=[cmd])

    async def patch_probe_config(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Patch liveness/readiness probe timing on a deployment."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] patch_probe_config skipped", params=params)
            return FixResult(success=True, fix_id=fix_id, action="patch_probe_config")

        namespace = params.get("namespace", "default")
        name = params.get("name", "")
        container = params.get("container", "")
        probe_type = params.get("probe_type", "livenessProbe")  # livenessProbe or readinessProbe
        initial_delay = params.get("initial_delay_seconds")
        timeout = params.get("timeout_seconds")
        period = params.get("period_seconds")
        failure_threshold = params.get("failure_threshold")

        probe_patch: dict[str, Any] = {}
        if initial_delay is not None:
            probe_patch["initialDelaySeconds"] = int(initial_delay)
        if timeout is not None:
            probe_patch["timeoutSeconds"] = int(timeout)
        if period is not None:
            probe_patch["periodSeconds"] = int(period)
        if failure_threshold is not None:
            probe_patch["failureThreshold"] = int(failure_threshold)

        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container,
                                probe_type: probe_patch,
                            }
                        ]
                    }
                }
            }
        }
        cmd = f"kubectl patch deployment {name} -n {namespace} --patch '{json.dumps(patch)}'"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=patch
                ),
            )
            logger.info("Probe config patched", name=name, namespace=namespace, probe_type=probe_type)
            return FixResult(success=True, fix_id=fix_id, action="patch_probe_config", kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="patch_probe_config",
                             error=str(exc), kubectl_commands=[cmd])

    async def restart_coredns(self, params: dict[str, Any], fix_id: str) -> FixResult:
        """Restart CoreDNS pods in kube-system."""
        if runtime_config.get("DRY_RUN", settings.DRY_RUN):
            logger.info("[DRY_RUN] restart_coredns skipped")
            return FixResult(success=True, fix_id=fix_id, action="restart_coredns")

        namespace = "kube-system"
        label_selector = "k8s-app=kube-dns"
        cmd = f"kubectl rollout restart deployment/coredns -n {namespace}"

        try:
            loop = asyncio.get_event_loop()
            pods = await loop.run_in_executor(
                None,
                lambda: self.core_v1.list_namespaced_pod(
                    namespace=namespace, label_selector=label_selector
                ),
            )
            for pod in pods.items:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda p=pod: self.core_v1.delete_namespaced_pod(
                            name=p.metadata.name, namespace=namespace
                        ),
                    )
                except ApiException:
                    pass
            logger.info("CoreDNS pods restarted")
            return FixResult(success=True, fix_id=fix_id, action="restart_coredns",
                             kubectl_commands=[cmd])
        except ApiException as exc:
            return FixResult(success=False, fix_id=fix_id, action="restart_coredns",
                             error=str(exc), kubectl_commands=[cmd])
