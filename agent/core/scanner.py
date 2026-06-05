"""Kubernetes cluster scanner — discovers incidents and emits them to the work queue."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from config.settings import settings
from db.connection import get_pool
from db.repos.incidents import get_open_incident

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Problem type constants
# ---------------------------------------------------------------------------

PROBLEM_TYPES: dict[str, str] = {
    "CRASH_LOOP_BACKOFF": "CrashLoopBackOff",
    "IMAGE_PULL_BACKOFF": "ImagePullBackOff",
    "ERR_IMAGE_PULL": "ErrImagePull",
    "OOM_KILLED": "OOMKilled",
    "APP_CRASH": "AppCrash",
    "ENTRYPOINT_ERROR": "EntrypointError",
    "CREATE_CONTAINER_CONFIG_ERROR": "CreateContainerConfigError",
    "CREATE_CONTAINER_ERROR": "CreateContainerError",
    "PENDING_TOO_LONG": "PendingTooLong",
    "HIGH_RESTART_COUNT": "HighRestartCount",
    "INIT_CONTAINER_FAILURE": "InitContainerFailure",
    "POD_EVICTED": "PodEvicted",
    "POD_STUCK_TERMINATING": "PodStuckTerminating",
    "CONTAINER_CREATING_STUCK": "ContainerCreatingStuck",
    "DEPLOYMENT_REPLICA_MISMATCH": "DeploymentReplicaMismatch",
    "DEPLOYMENT_ROLLOUT_STUCK": "DeploymentRolloutStuck",
    "DEPLOYMENT_PAUSED": "DeploymentPaused",
    "NODE_NOT_READY": "NodeNotReady",
    "NODE_MEMORY_PRESSURE": "NodeMemoryPressure",
    "NODE_DISK_PRESSURE": "NodeDiskPressure",
    "NODE_PID_PRESSURE": "NodePIDPressure",
    "NODE_RESOURCE_EXHAUSTION": "NodeResourceExhaustion",
    "SERVICE_NO_ENDPOINTS": "ServiceNoEndpoints",
    "SERVICE_SELECTOR_MISMATCH": "ServiceSelectorMismatch",
    "PVC_PENDING": "PVCPending",
    "PVC_LOST": "PVCLost",
    "RESOURCE_QUOTA_NEAR_LIMIT": "ResourceQuotaNearLimit",
    "RESOURCE_QUOTA_EXCEEDED": "ResourceQuotaExceeded",
    "HPA_SCALE_BLOCKED": "HPAScaleBlocked",
    "HPA_AT_MAX": "HPAAtMax",
    "HPA_METRICS_SERVER_ISSUE": "HPAMetricsServerIssue",
    "INGRESS_NO_LB": "IngressNoLB",
    "INGRESS_BACKEND_MISSING": "IngressBackendMissing",
    "INGRESS_TLS_INVALID": "IngressTLSInvalid",
    "STATEFULSET_UPDATE_STUCK": "StatefulSetUpdateStuck",
    "JOB_FAILED": "JobFailed",
    "CRONJOB_MISSED": "CronJobMissed",
    "CASCADING_FAILURE": "CascadingFailure",
}

_KUBE_SYSTEM_SAFE_NAMES = {"coredns", "metrics-server"}


class ClusterScanner:
    """Polls all target namespaces for unhealthy resources and emits incidents."""

    def __init__(self) -> None:
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        self.core_v1 = k8s_client.CoreV1Api()
        self.apps_v1 = k8s_client.AppsV1Api()
        self.batch_v1 = k8s_client.BatchV1Api()
        self.autoscaling_v1 = k8s_client.AutoscalingV1Api()
        self.networking_v1 = k8s_client.NetworkingV1Api()
        self._redis_client: aioredis.Redis | None = None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def scan_all_namespaces(self) -> None:
        """Top-level scan cycle; called by APScheduler every SCAN_INTERVAL_SECONDS."""
        logger.info("Starting cluster scan cycle")
        try:
            self._redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as exc:
            logger.error("Failed to connect to Redis", error=str(exc))
            return

        namespaces = settings.target_namespaces_list

        try:
            # Node-level checks run once, not per-namespace
            node_incidents = await asyncio.get_event_loop().run_in_executor(
                None, self._scan_nodes_sync
            )
            for incident in node_incidents:
                await self._process_incident(incident)

            for namespace in namespaces:
                await self._scan_namespace(namespace)

            # Cross-service cascade analysis
            cascade_incidents = await self.cross_service_analyzer()
            for incident in cascade_incidents:
                await self._process_incident(incident)

        except Exception as exc:
            logger.exception("Unhandled error in scan_all_namespaces", error=str(exc))
        finally:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None
            logger.info("Cluster scan cycle complete")

    async def _scan_namespace(self, namespace: str) -> None:
        """Run all per-namespace checks, logging but never crashing on individual failures."""
        scanners = [
            self.scan_pods,
            self.scan_deployments,
            self.scan_services,
            self.scan_pvcs,
            self.scan_resource_quotas,
            self.scan_hpas,
            self.scan_ingresses,
            self.scan_statefulsets,
            self.scan_jobs,
        ]
        for scanner_fn in scanners:
            try:
                incidents = await asyncio.get_event_loop().run_in_executor(
                    None, lambda fn=scanner_fn, ns=namespace: asyncio.run(_run_sync(fn, ns))
                )
                for incident in incidents or []:
                    await self._process_incident(incident)
            except Exception as exc:
                logger.warning(
                    "Scanner failed for namespace",
                    scanner=scanner_fn.__name__,
                    namespace=namespace,
                    error=str(exc),
                )

    async def _process_incident(self, incident: dict[str, Any]) -> None:
        """Deduplicate and emit an incident to the Redis queue."""
        try:
            pool = await get_pool()
            existing = await get_open_incident(
                pool,
                incident["resource_type"],
                incident["resource_name"],
                incident["namespace"],
                incident["problem_type"],
            )
            if existing:
                logger.debug(
                    "Deduplicating incident (already open)",
                    resource=incident["resource_name"],
                    problem=incident["problem_type"],
                )
                return
            await self.emit_incident(self._redis_client, incident)
        except Exception as exc:
            logger.error("Error processing incident", error=str(exc), incident=incident)

    # ------------------------------------------------------------------
    # Pod scanning
    # ------------------------------------------------------------------

    def scan_pods(self, namespace: str) -> list[dict[str, Any]]:  # noqa: C901
        """Scan all pods in *namespace* for failure conditions."""
        incidents: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        try:
            pods = self.core_v1.list_namespaced_pod(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list pods", namespace=namespace, error=str(exc))
            return incidents

        for pod in pods.items:
            pod_name: str = pod.metadata.name
            pod_ns: str = pod.metadata.namespace or namespace

            # Skip kube-system pods unless they are coredns/metrics-server
            if pod_ns == "kube-system":
                safe = any(s in pod_name.lower() for s in _KUBE_SYSTEM_SAFE_NAMES)
                if not safe:
                    continue

            try:
                # Evicted pods
                if pod.status and pod.status.phase == "Failed":
                    reason = pod.status.reason or ""
                    if reason == "Evicted":
                        incidents.append(
                            self._make_incident(
                                "pod", pod_name, pod_ns,
                                PROBLEM_TYPES["POD_EVICTED"],
                                "MEDIUM",
                                {"message": pod.status.message or ""},
                            )
                        )
                        continue

                # Stuck terminating
                if pod.metadata.deletion_timestamp:
                    age_sec = (now - pod.metadata.deletion_timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                    if age_sec > 300:  # 5 min
                        incidents.append(
                            self._make_incident(
                                "pod", pod_name, pod_ns,
                                PROBLEM_TYPES["POD_STUCK_TERMINATING"],
                                "MEDIUM",
                                {"deletion_age_seconds": int(age_sec)},
                            )
                        )
                        continue

                if not pod.status or not pod.status.container_statuses:
                    # Check for Pending > 5 min
                    if pod.status and pod.status.phase == "Pending":
                        start = pod.status.start_time
                        if start:
                            age_sec = (now - start.replace(tzinfo=timezone.utc)).total_seconds()
                            if age_sec > 300:
                                incidents.append(
                                    self._make_incident(
                                        "pod", pod_name, pod_ns,
                                        PROBLEM_TYPES["PENDING_TOO_LONG"],
                                        "HIGH",
                                        {"pending_seconds": int(age_sec)},
                                    )
                                )
                    # Check init containers
                    self._check_init_containers(pod, pod_ns, incidents, now)
                    continue

                for cs in pod.status.container_statuses:
                    waiting = cs.state.waiting if cs.state else None
                    terminated = cs.state.terminated if cs.state else None

                    # ContainerCreating stuck > 3 min
                    if waiting and waiting.reason == "ContainerCreating":
                        start = pod.status.start_time
                        if start:
                            age_sec = (now - start.replace(tzinfo=timezone.utc)).total_seconds()
                            if age_sec > 180:
                                incidents.append(
                                    self._make_incident(
                                        "pod", pod_name, pod_ns,
                                        PROBLEM_TYPES["CONTAINER_CREATING_STUCK"],
                                        "HIGH",
                                        {"container": cs.name, "age_seconds": int(age_sec)},
                                    )
                                )

                    elif waiting:
                        reason = waiting.reason or ""
                        msg = waiting.message or ""

                        if reason == "CrashLoopBackOff":
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["CRASH_LOOP_BACKOFF"],
                                    "HIGH",
                                    {"container": cs.name, "restart_count": cs.restart_count, "message": msg},
                                )
                            )
                        elif reason in ("ImagePullBackOff", "ErrImagePull"):
                            prob_key = "IMAGE_PULL_BACKOFF" if reason == "ImagePullBackOff" else "ERR_IMAGE_PULL"
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES[prob_key],
                                    "HIGH",
                                    {"container": cs.name, "image": cs.image, "message": msg},
                                )
                            )
                        elif reason == "CreateContainerConfigError":
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["CREATE_CONTAINER_CONFIG_ERROR"],
                                    "HIGH",
                                    {"container": cs.name, "message": msg},
                                )
                            )
                        elif reason == "CreateContainerError":
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["CREATE_CONTAINER_ERROR"],
                                    "HIGH",
                                    {"container": cs.name, "message": msg},
                                )
                            )

                    if terminated:
                        exit_code = terminated.exit_code
                        if exit_code == 137:
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["OOM_KILLED"],
                                    "HIGH",
                                    {"container": cs.name, "exit_code": exit_code},
                                )
                            )
                        elif exit_code == 1:
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["APP_CRASH"],
                                    "HIGH",
                                    {"container": cs.name, "exit_code": exit_code},
                                )
                            )
                        elif exit_code in (126, 127):
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["ENTRYPOINT_ERROR"],
                                    "HIGH",
                                    {"container": cs.name, "exit_code": exit_code},
                                )
                            )

                    # High restart count
                    if cs.restart_count and cs.restart_count > 5:
                        incidents.append(
                            self._make_incident(
                                "pod", pod_name, pod_ns,
                                PROBLEM_TYPES["HIGH_RESTART_COUNT"],
                                "MEDIUM",
                                {"container": cs.name, "restart_count": cs.restart_count},
                            )
                        )

                # Pending pod
                if pod.status.phase == "Pending":
                    start = pod.status.start_time
                    if start:
                        age_sec = (now - start.replace(tzinfo=timezone.utc)).total_seconds()
                        if age_sec > 300:
                            incidents.append(
                                self._make_incident(
                                    "pod", pod_name, pod_ns,
                                    PROBLEM_TYPES["PENDING_TOO_LONG"],
                                    "HIGH",
                                    {"pending_seconds": int(age_sec)},
                                )
                            )

                # Init containers
                self._check_init_containers(pod, pod_ns, incidents, now)

            except Exception as exc:
                logger.warning("Error scanning pod", pod=pod_name, error=str(exc))

        return incidents

    def _check_init_containers(
        self,
        pod: Any,
        namespace: str,
        incidents: list[dict[str, Any]],
        now: datetime,
    ) -> None:
        if not pod.status or not pod.status.init_container_statuses:
            return
        for ics in pod.status.init_container_statuses:
            if ics.state and ics.state.waiting:
                reason = ics.state.waiting.reason or ""
                if reason in ("CrashLoopBackOff", "Error"):
                    incidents.append(
                        self._make_incident(
                            "pod", pod.metadata.name, namespace,
                            PROBLEM_TYPES["INIT_CONTAINER_FAILURE"],
                            "HIGH",
                            {
                                "init_container": ics.name,
                                "reason": reason,
                                "restart_count": ics.restart_count,
                            },
                        )
                    )

    # ------------------------------------------------------------------
    # Deployment scanning
    # ------------------------------------------------------------------

    def scan_deployments(self, namespace: str) -> list[dict[str, Any]]:
        """Scan deployments for replica mismatches, stuck rollouts, and paused state."""
        incidents: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list deployments", namespace=namespace, error=str(exc))
            return incidents

        for dep in deployments.items:
            name = dep.metadata.name
            try:
                spec_replicas = dep.spec.replicas or 1
                status = dep.status

                if dep.spec.paused:
                    incidents.append(
                        self._make_incident(
                            "deployment", name, namespace,
                            PROBLEM_TYPES["DEPLOYMENT_PAUSED"],
                            "LOW",
                            {"message": "Deployment is paused"},
                        )
                    )
                    continue

                available = status.available_replicas or 0
                if available < spec_replicas:
                    # Check how long the rollout has been stuck
                    for cond in (status.conditions or []):
                        if cond.type == "Progressing" and cond.status == "False":
                            incidents.append(
                                self._make_incident(
                                    "deployment", name, namespace,
                                    PROBLEM_TYPES["DEPLOYMENT_ROLLOUT_STUCK"],
                                    "HIGH",
                                    {
                                        "desired": spec_replicas,
                                        "available": available,
                                        "message": cond.message or "",
                                    },
                                )
                            )
                            break
                    else:
                        if available < spec_replicas:
                            incidents.append(
                                self._make_incident(
                                    "deployment", name, namespace,
                                    PROBLEM_TYPES["DEPLOYMENT_REPLICA_MISMATCH"],
                                    "MEDIUM",
                                    {"desired": spec_replicas, "available": available},
                                )
                            )
            except Exception as exc:
                logger.warning("Error scanning deployment", deployment=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Node scanning
    # ------------------------------------------------------------------

    def _scan_nodes_sync(self) -> list[dict[str, Any]]:
        return self.scan_nodes()

    def scan_nodes(self) -> list[dict[str, Any]]:
        """Scan cluster nodes for pressure conditions and NotReady status."""
        incidents: list[dict[str, Any]] = []

        try:
            nodes = self.core_v1.list_node()
        except ApiException as exc:
            logger.warning("Cannot list nodes", error=str(exc))
            return incidents

        for node in nodes.items:
            name = node.metadata.name
            try:
                for cond in (node.status.conditions or []):
                    if cond.status != "True":
                        continue
                    problem_map = {
                        "MemoryPressure": ("NODE_MEMORY_PRESSURE", "HIGH"),
                        "DiskPressure": ("NODE_DISK_PRESSURE", "HIGH"),
                        "PIDPressure": ("NODE_PID_PRESSURE", "MEDIUM"),
                    }
                    if cond.type in problem_map:
                        key, sev = problem_map[cond.type]
                        incidents.append(
                            self._make_incident(
                                "node", name, "cluster",
                                PROBLEM_TYPES[key],
                                sev,
                                {"condition": cond.type, "message": cond.message or ""},
                            )
                        )

                for cond in (node.status.conditions or []):
                    if cond.type == "Ready" and cond.status != "True":
                        incidents.append(
                            self._make_incident(
                                "node", name, "cluster",
                                PROBLEM_TYPES["NODE_NOT_READY"],
                                "CRITICAL",
                                {"reason": cond.reason or "", "message": cond.message or ""},
                            )
                        )

            except Exception as exc:
                logger.warning("Error scanning node", node=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Service scanning
    # ------------------------------------------------------------------

    def scan_services(self, namespace: str) -> list[dict[str, Any]]:
        """Check services for missing endpoints and selector mismatches."""
        incidents: list[dict[str, Any]] = []

        try:
            services = self.core_v1.list_namespaced_service(namespace=namespace)
            endpoints = self.core_v1.list_namespaced_endpoints(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list services/endpoints", namespace=namespace, error=str(exc))
            return incidents

        ep_map: dict[str, Any] = {ep.metadata.name: ep for ep in endpoints.items}

        for svc in services.items:
            name = svc.metadata.name
            # Skip ClusterIP=None (headless) and kube-system
            if name in ("kubernetes",) or namespace == "kube-system":
                continue
            try:
                ep = ep_map.get(name)
                if not ep:
                    continue
                has_endpoints = bool(
                    ep.subsets and any(s.addresses for s in ep.subsets)
                )
                if not has_endpoints and svc.spec.selector:
                    incidents.append(
                        self._make_incident(
                            "service", name, namespace,
                            PROBLEM_TYPES["SERVICE_NO_ENDPOINTS"],
                            "HIGH",
                            {"selector": svc.spec.selector},
                        )
                    )
            except Exception as exc:
                logger.warning("Error scanning service", service=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # PVC scanning
    # ------------------------------------------------------------------

    def scan_pvcs(self, namespace: str) -> list[dict[str, Any]]:
        """Check PVCs for Pending > 5 min and Lost phase."""
        incidents: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        try:
            pvcs = self.core_v1.list_namespaced_persistent_volume_claim(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list PVCs", namespace=namespace, error=str(exc))
            return incidents

        for pvc in pvcs.items:
            name = pvc.metadata.name
            try:
                phase = pvc.status.phase
                if phase == "Lost":
                    incidents.append(
                        self._make_incident(
                            "pvc", name, namespace,
                            PROBLEM_TYPES["PVC_LOST"],
                            "CRITICAL",
                            {"storage_class": pvc.spec.storage_class_name},
                        )
                    )
                elif phase == "Pending":
                    created = pvc.metadata.creation_timestamp
                    if created:
                        age_sec = (now - created.replace(tzinfo=timezone.utc)).total_seconds()
                        if age_sec > 300:
                            incidents.append(
                                self._make_incident(
                                    "pvc", name, namespace,
                                    PROBLEM_TYPES["PVC_PENDING"],
                                    "HIGH",
                                    {
                                        "pending_seconds": int(age_sec),
                                        "storage_class": pvc.spec.storage_class_name,
                                    },
                                )
                            )
            except Exception as exc:
                logger.warning("Error scanning PVC", pvc=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Resource quota scanning
    # ------------------------------------------------------------------

    def scan_resource_quotas(self, namespace: str) -> list[dict[str, Any]]:
        """Alert when resource quotas are >= 90% used or fully exceeded."""
        incidents: list[dict[str, Any]] = []

        try:
            quotas = self.core_v1.list_namespaced_resource_quota(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list resource quotas", namespace=namespace, error=str(exc))
            return incidents

        for quota in quotas.items:
            name = quota.metadata.name
            try:
                hard = quota.status.hard or {}
                used = quota.status.used or {}
                for resource, hard_val in hard.items():
                    used_val = used.get(resource)
                    if not used_val:
                        continue
                    hard_n = _parse_resource_quantity(str(hard_val))
                    used_n = _parse_resource_quantity(str(used_val))
                    if hard_n <= 0:
                        continue
                    pct = used_n / hard_n
                    if pct >= 1.0:
                        incidents.append(
                            self._make_incident(
                                "resourcequota", name, namespace,
                                PROBLEM_TYPES["RESOURCE_QUOTA_EXCEEDED"],
                                "CRITICAL",
                                {"resource": resource, "used": str(used_val), "hard": str(hard_val)},
                            )
                        )
                    elif pct >= 0.9:
                        incidents.append(
                            self._make_incident(
                                "resourcequota", name, namespace,
                                PROBLEM_TYPES["RESOURCE_QUOTA_NEAR_LIMIT"],
                                "HIGH",
                                {
                                    "resource": resource,
                                    "used": str(used_val),
                                    "hard": str(hard_val),
                                    "pct": round(pct * 100, 1),
                                },
                            )
                        )
            except Exception as exc:
                logger.warning("Error scanning resource quota", quota=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # HPA scanning
    # ------------------------------------------------------------------

    def scan_hpas(self, namespace: str) -> list[dict[str, Any]]:
        """Check HPAs for scale-blocked, at-max, and metrics-server issues."""
        incidents: list[dict[str, Any]] = []

        try:
            hpas = self.autoscaling_v1.list_namespaced_horizontal_pod_autoscaler(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list HPAs", namespace=namespace, error=str(exc))
            return incidents

        for hpa in hpas.items:
            name = hpa.metadata.name
            try:
                status = hpa.status
                spec = hpa.spec
                current = status.current_replicas or 0
                desired = status.desired_replicas or 0
                max_r = spec.max_replicas or 0

                # At max replicas
                if current >= max_r and max_r > 0:
                    incidents.append(
                        self._make_incident(
                            "hpa", name, namespace,
                            PROBLEM_TYPES["HPA_AT_MAX"],
                            "MEDIUM",
                            {"current": current, "max": max_r},
                        )
                    )

                # Metrics server issue (currentCPUUtilizationPercentage is None)
                if status.current_cpu_utilization_percentage is None and current > 0:
                    incidents.append(
                        self._make_incident(
                            "hpa", name, namespace,
                            PROBLEM_TYPES["HPA_METRICS_SERVER_ISSUE"],
                            "HIGH",
                            {"message": "HPA cannot read metrics — metrics-server may be down"},
                        )
                    )

            except Exception as exc:
                logger.warning("Error scanning HPA", hpa=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Ingress scanning
    # ------------------------------------------------------------------

    def scan_ingresses(self, namespace: str) -> list[dict[str, Any]]:
        """Check ingresses for missing LB, backend issues, and TLS problems."""
        incidents: list[dict[str, Any]] = []

        try:
            ingresses = self.networking_v1.list_namespaced_ingress(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list ingresses", namespace=namespace, error=str(exc))
            return incidents

        for ing in ingresses.items:
            name = ing.metadata.name
            try:
                # No load-balancer IP assigned
                lb_ingress = ing.status.load_balancer.ingress if ing.status.load_balancer else None
                if not lb_ingress:
                    incidents.append(
                        self._make_incident(
                            "ingress", name, namespace,
                            PROBLEM_TYPES["INGRESS_NO_LB"],
                            "MEDIUM",
                            {"message": "No LoadBalancer IP/hostname assigned yet"},
                        )
                    )

                # TLS secrets referenced but may not exist
                for tls in (ing.spec.tls or []):
                    secret_name = tls.secret_name
                    if secret_name:
                        try:
                            self.core_v1.read_namespaced_secret(name=secret_name, namespace=namespace)
                        except ApiException:
                            incidents.append(
                                self._make_incident(
                                    "ingress", name, namespace,
                                    PROBLEM_TYPES["INGRESS_TLS_INVALID"],
                                    "HIGH",
                                    {"missing_secret": secret_name},
                                )
                            )

            except Exception as exc:
                logger.warning("Error scanning ingress", ingress=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # StatefulSet scanning
    # ------------------------------------------------------------------

    def scan_statefulsets(self, namespace: str) -> list[dict[str, Any]]:
        """Check StatefulSets for stuck updates."""
        incidents: list[dict[str, Any]] = []

        try:
            statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list statefulsets", namespace=namespace, error=str(exc))
            return incidents

        for sts in statefulsets.items:
            name = sts.metadata.name
            try:
                spec_replicas = sts.spec.replicas or 1
                ready = sts.status.ready_replicas or 0
                updated = sts.status.updated_replicas or 0
                current_revision = sts.status.current_revision or ""
                update_revision = sts.status.update_revision or ""

                if current_revision != update_revision and updated < spec_replicas:
                    incidents.append(
                        self._make_incident(
                            "statefulset", name, namespace,
                            PROBLEM_TYPES["STATEFULSET_UPDATE_STUCK"],
                            "HIGH",
                            {
                                "desired": spec_replicas,
                                "updated": updated,
                                "ready": ready,
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("Error scanning statefulset", statefulset=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Job / CronJob scanning
    # ------------------------------------------------------------------

    def scan_jobs(self, namespace: str) -> list[dict[str, Any]]:
        """Check Jobs for failures and CronJobs for missed schedules."""
        incidents: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        try:
            jobs = self.batch_v1.list_namespaced_job(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list jobs", namespace=namespace, error=str(exc))
            return incidents

        for job in jobs.items:
            name = job.metadata.name
            try:
                if job.status.failed and job.status.failed > 0:
                    # Only alert if there's no active pods (truly failed, not retrying)
                    active = job.status.active or 0
                    if active == 0 and not job.status.completion_time:
                        incidents.append(
                            self._make_incident(
                                "job", name, namespace,
                                PROBLEM_TYPES["JOB_FAILED"],
                                "HIGH",
                                {"failed_count": job.status.failed},
                            )
                        )
            except Exception as exc:
                logger.warning("Error scanning job", job=name, error=str(exc))

        try:
            cronjobs = self.batch_v1.list_namespaced_cron_job(namespace=namespace)
        except ApiException as exc:
            logger.warning("Cannot list cronjobs", namespace=namespace, error=str(exc))
            return incidents

        for cj in cronjobs.items:
            name = cj.metadata.name
            try:
                last_schedule = cj.status.last_schedule_time
                if last_schedule:
                    age_sec = (now - last_schedule.replace(tzinfo=timezone.utc)).total_seconds()
                    # If last schedule was > 2 hours ago and no active jobs
                    active_jobs = cj.status.active or []
                    if age_sec > 7200 and not active_jobs:
                        incidents.append(
                            self._make_incident(
                                "cronjob", name, namespace,
                                PROBLEM_TYPES["CRONJOB_MISSED"],
                                "MEDIUM",
                                {"last_schedule_age_seconds": int(age_sec)},
                            )
                        )
            except Exception as exc:
                logger.warning("Error scanning cronjob", cronjob=name, error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Cross-service cascade analysis
    # ------------------------------------------------------------------

    async def cross_service_analyzer(self) -> list[dict[str, Any]]:
        """Detect cascading failures across namespaces (e.g. DNS is down → many pods fail)."""
        incidents: list[dict[str, Any]] = []

        try:
            all_pods: list[Any] = []
            for ns in settings.target_namespaces_list:
                try:
                    pods = self.core_v1.list_namespaced_pod(namespace=ns)
                    all_pods.extend(pods.items)
                except ApiException:
                    pass

            crash_by_ns: dict[str, int] = {}
            for pod in all_pods:
                if not pod.status or not pod.status.container_statuses:
                    continue
                for cs in pod.status.container_statuses:
                    if cs.state and cs.state.waiting and cs.state.waiting.reason == "CrashLoopBackOff":
                        ns = pod.metadata.namespace
                        crash_by_ns[ns] = crash_by_ns.get(ns, 0) + 1

            for ns, count in crash_by_ns.items():
                if count >= 5:
                    incidents.append(
                        self._make_incident(
                            "namespace", ns, ns,
                            PROBLEM_TYPES["CASCADING_FAILURE"],
                            "CRITICAL",
                            {"crash_count": count, "message": f"{count} pods in CrashLoopBackOff — possible DNS or config issue"},
                        )
                    )
        except Exception as exc:
            logger.warning("Error in cross_service_analyzer", error=str(exc))

        return incidents

    # ------------------------------------------------------------------
    # Context collection
    # ------------------------------------------------------------------

    def collect_pod_context(self, namespace: str, pod_name: str) -> dict[str, Any]:
        """Fetch recent logs and events for a pod to enrich the incident context."""
        context: dict[str, Any] = {}

        # Logs (last 100 lines)
        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=100,
                previous=False,
            )
            context["logs"] = logs
        except ApiException:
            try:
                logs = self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=50,
                    previous=True,
                )
                context["previous_logs"] = logs
            except ApiException:
                context["logs"] = "unavailable"

        # Events
        try:
            events = self.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.name={pod_name}",
            )
            context["events"] = [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "message": e.message,
                    "count": e.count,
                    "last_time": str(e.last_timestamp),
                }
                for e in events.items
            ]
        except ApiException:
            context["events"] = []

        return context

    # ------------------------------------------------------------------
    # Deduplication helper (sync wrapper around async repo call)
    # ------------------------------------------------------------------

    async def deduplicate_incident(self, pool: Any, incident: dict[str, Any]) -> bool:
        """Return True if an open incident already exists for this resource+problem."""
        existing = await get_open_incident(
            pool,
            incident["resource_type"],
            incident["resource_name"],
            incident["namespace"],
            incident["problem_type"],
        )
        return existing is not None

    # ------------------------------------------------------------------
    # Redis emit
    # ------------------------------------------------------------------

    async def emit_incident(
        self,
        redis_client: aioredis.Redis,
        incident: dict[str, Any],
    ) -> None:
        """Push the incident JSON to the autopilot:incident_queue Redis list."""
        payload = json.dumps(incident, default=str)
        await redis_client.lpush("autopilot:incident_queue", payload)
        await redis_client.publish("autopilot:events", json.dumps({
            "event": "incident_detected",
            "resource": incident.get("resource_name"),
            "namespace": incident.get("namespace"),
            "problem_type": incident.get("problem_type"),
        }))
        logger.info(
            "Incident emitted to queue",
            resource=incident.get("resource_name"),
            problem=incident.get("problem_type"),
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _make_incident(
        resource_type: str,
        resource_name: str,
        namespace: str,
        problem_type: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "namespace": namespace,
            "problem_type": problem_type,
            "severity": severity,
            "context": context or {},
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_sync(fn: Any, ns: str) -> list[dict[str, Any]]:
    return fn(ns)


def _parse_resource_quantity(value: str) -> float:
    """Parse a Kubernetes resource quantity string to a float."""
    value = value.strip()
    multipliers = {
        "Ki": 1024, "Mi": 1024 ** 2, "Gi": 1024 ** 3, "Ti": 1024 ** 4,
        "k": 1000, "M": 1000 ** 2, "G": 1000 ** 3,
        "m": 0.001,
    }
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return float(value[: -len(suffix)]) * mult
            except ValueError:
                return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0
