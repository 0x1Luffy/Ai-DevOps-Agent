"""FeedbackLoop — verifies whether a fix actually resolved the incident."""

from __future__ import annotations

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
from db.repos.fixes import update_fix_execution
from db.repos.incidents import get_incident, update_incident_status

logger = structlog.get_logger(__name__)


class FeedbackLoop:
    """Verifies fix outcomes and updates the database accordingly."""

    def __init__(self) -> None:
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        self.core_v1 = k8s_client.CoreV1Api()
        self.apps_v1 = k8s_client.AppsV1Api()
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def verify_fix(
        self,
        incident_id: str,
        fix_id: str,
        namespace: str | None = None,
        resource_type: str | None = None,
        resource_name: str | None = None,
    ) -> str:
        """
        Check whether the resource is now healthy.

        Returns one of: 'fixed', 'still_broken', 'degraded', 'pending', 'skipped'.
        """
        pool = await get_pool()

        # Fetch incident details if not provided
        if not all([namespace, resource_type, resource_name]):
            incident = await get_incident(pool, incident_id)
            if not incident:
                logger.warning("Incident not found during verification", incident_id=incident_id)
                return "skipped"
            namespace = namespace or incident.get("namespace", "default")
            resource_type = resource_type or incident.get("resource_type", "")
            resource_name = resource_name or incident.get("resource_name", "")

        logger.info(
            "Verifying fix outcome",
            incident_id=incident_id,
            fix_id=fix_id,
            resource=resource_name,
            resource_type=resource_type,
            namespace=namespace,
        )

        verification_status = "pending"
        try:
            if resource_type == "pod":
                verification_status = await self._verify_pod(namespace, resource_name)
            elif resource_type == "deployment":
                verification_status = await self._verify_deployment(namespace, resource_name)
            elif resource_type == "node":
                verification_status = await self._verify_node(resource_name)
            elif resource_type == "service":
                verification_status = await self._verify_service(namespace, resource_name)
            elif resource_type in ("statefulset",):
                verification_status = await self._verify_statefulset(namespace, resource_name)
            else:
                verification_status = "skipped"
        except Exception as exc:
            logger.warning("Error during fix verification", error=str(exc))
            verification_status = "pending"

        # Update fix_execution
        await update_fix_execution(
            pool,
            fix_id,
            verification_status=verification_status,
            verified_at=datetime.now(timezone.utc),
        )

        # Update incident status
        if verification_status == "fixed":
            await update_incident_status(
                pool,
                incident_id,
                "fixed",
                resolved_at=datetime.now(timezone.utc),
            )
        elif verification_status == "still_broken":
            await update_incident_status(pool, incident_id, "still_broken")
        elif verification_status == "degraded":
            await update_incident_status(pool, incident_id, "still_broken")

        # Publish result
        redis_client = await self._get_redis()
        await redis_client.publish(
            "autopilot:events",
            json.dumps({
                "event": "fix_verified",
                "incident_id": incident_id,
                "fix_id": fix_id,
                "verification_status": verification_status,
                "resource": resource_name,
                "namespace": namespace,
            }),
        )

        logger.info(
            "Fix verification complete",
            incident_id=incident_id,
            verification_status=verification_status,
        )
        return verification_status

    # ------------------------------------------------------------------
    # Resource-specific health checks
    # ------------------------------------------------------------------

    async def _verify_pod(self, namespace: str, pod_name: str) -> str:
        """Check if a pod is now Running and ready."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            pod = await loop.run_in_executor(
                None,
                lambda: self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace),
            )
            phase = pod.status.phase if pod.status else "Unknown"
            if phase == "Running":
                # Check readiness
                if pod.status.container_statuses:
                    all_ready = all(cs.ready for cs in pod.status.container_statuses)
                    return "fixed" if all_ready else "degraded"
                return "fixed"
            elif phase in ("Failed", "Unknown"):
                return "still_broken"
            return "pending"
        except ApiException as exc:
            if exc.status == 404:
                # Pod was deleted and hasn't been recreated yet
                return "pending"
            return "still_broken"

    async def _verify_deployment(self, namespace: str, deployment_name: str) -> str:
        """Check if a deployment now has all replicas available."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            dep = await loop.run_in_executor(
                None,
                lambda: self.apps_v1.read_namespaced_deployment(
                    name=deployment_name, namespace=namespace
                ),
            )
            desired = dep.spec.replicas or 1
            available = dep.status.available_replicas or 0
            ready = dep.status.ready_replicas or 0

            if available >= desired and ready >= desired:
                return "fixed"
            elif available > 0:
                return "degraded"
            return "still_broken"
        except ApiException as exc:
            if exc.status == 404:
                return "still_broken"
            return "pending"

    async def _verify_node(self, node_name: str) -> str:
        """Check if a node is Ready."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            node = await loop.run_in_executor(
                None,
                lambda: self.core_v1.read_node(name=node_name),
            )
            for cond in (node.status.conditions or []):
                if cond.type == "Ready":
                    return "fixed" if cond.status == "True" else "still_broken"
            return "pending"
        except ApiException:
            return "still_broken"

    async def _verify_service(self, namespace: str, svc_name: str) -> str:
        """Check if a service has active endpoints."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            ep = await loop.run_in_executor(
                None,
                lambda: self.core_v1.read_namespaced_endpoints(
                    name=svc_name, namespace=namespace
                ),
            )
            has_endpoints = bool(
                ep.subsets and any(s.addresses for s in ep.subsets)
            )
            return "fixed" if has_endpoints else "still_broken"
        except ApiException:
            return "still_broken"

    async def _verify_statefulset(self, namespace: str, sts_name: str) -> str:
        """Check if a StatefulSet is fully up-to-date and ready."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            sts = await loop.run_in_executor(
                None,
                lambda: self.apps_v1.read_namespaced_stateful_set(
                    name=sts_name, namespace=namespace
                ),
            )
            desired = sts.spec.replicas or 1
            ready = sts.status.ready_replicas or 0
            if ready >= desired:
                return "fixed"
            elif ready > 0:
                return "degraded"
            return "still_broken"
        except ApiException:
            return "still_broken"
