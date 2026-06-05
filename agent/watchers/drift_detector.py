"""DriftDetector — detects configuration drift between desired and live state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from config.settings import settings
from db.connection import get_pool

logger = structlog.get_logger(__name__)


class DriftDetector:
    """Compares live Kubernetes state against the desired state recorded on deploy."""

    def __init__(self) -> None:
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        self.apps_v1 = k8s_client.AppsV1Api()

    # ------------------------------------------------------------------
    # Record desired state (called on successful Jenkins deploy)
    # ------------------------------------------------------------------

    async def record_desired_state(
        self,
        namespace: str,
        deployment_name: str,
        spec: dict[str, Any],
        recorded_by: str = "jenkins",
    ) -> None:
        """Persist the desired state snapshot for a deployment."""
        pool = await get_pool()

        # Extract structured fields for fast comparison
        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        image_tags: dict[str, str] = {}
        env_var_keys: list[str] = []
        resource_limits: dict[str, Any] = {}
        replica_count: int = spec.get("replicas", 1)

        for container in containers:
            image = container.get("image", "")
            if image:
                image_tags[container.get("name", "default")] = image

            for env in container.get("env", []):
                key = env.get("name", "")
                if key:
                    env_var_keys.append(key)

            resources = container.get("resources", {})
            if resources:
                resource_limits[container.get("name", "default")] = resources

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO desired_state (
                    resource_type, resource_name, namespace, spec_snapshot,
                    image_tags, env_var_keys, resource_limits, replica_count, recorded_by
                ) VALUES ('deployment', $1, $2, $3::jsonb, $4::jsonb, $5, $6::jsonb, $7, $8)
                ON CONFLICT (resource_type, resource_name, namespace)
                DO UPDATE SET
                    spec_snapshot = EXCLUDED.spec_snapshot,
                    image_tags = EXCLUDED.image_tags,
                    env_var_keys = EXCLUDED.env_var_keys,
                    resource_limits = EXCLUDED.resource_limits,
                    replica_count = EXCLUDED.replica_count,
                    recorded_at = NOW(),
                    recorded_by = EXCLUDED.recorded_by
                """,
                deployment_name,
                namespace,
                json.dumps(spec),
                json.dumps(image_tags),
                list(set(env_var_keys)),
                json.dumps(resource_limits),
                replica_count,
                recorded_by,
            )

        logger.info(
            "Desired state recorded",
            deployment=deployment_name,
            namespace=namespace,
            recorded_by=recorded_by,
        )

    # ------------------------------------------------------------------
    # Drift check (every 5 min)
    # ------------------------------------------------------------------

    async def check_drift(self) -> list[dict[str, Any]]:
        """Compare live state vs desired state for all tracked deployments."""
        pool = await get_pool()
        drift_events: list[dict[str, Any]] = []

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM desired_state WHERE resource_type = 'deployment'"
            )

        for row in rows:
            desired = dict(row)
            namespace = desired["namespace"]
            name = desired["resource_name"]

            try:
                import asyncio
                loop = asyncio.get_event_loop()
                live_dep = await loop.run_in_executor(
                    None,
                    lambda n=name, ns=namespace: self.apps_v1.read_namespaced_deployment(
                        name=n, namespace=ns
                    ),
                )
            except ApiException as exc:
                if exc.status == 404:
                    logger.warning("Desired deployment no longer exists", name=name, ns=namespace)
                continue
            except Exception as exc:
                logger.warning("Drift check error", name=name, error=str(exc))
                continue

            drifts = self._compare_state(desired, live_dep, namespace, name)
            drift_events.extend(drifts)

            if drifts:
                await self._record_drift_events(pool, drifts)

                if settings.DRIFT_AUTO_CORRECT:
                    for drift in drifts:
                        if drift["drift_type"] in ("image_tag_changed", "replica_count_changed"):
                            await self.auto_correct_drift(namespace, name, desired)
                            break

        if drift_events:
            logger.info("Drift detected", count=len(drift_events))
        return drift_events

    def _compare_state(
        self,
        desired: dict[str, Any],
        live: Any,
        namespace: str,
        name: str,
    ) -> list[dict[str, Any]]:
        """Return a list of drift events by comparing desired vs live fields."""
        drifts: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        desired_images: dict[str, str] = desired.get("image_tags") or {}
        if isinstance(desired_images, str):
            desired_images = json.loads(desired_images)

        desired_replicas: int = desired.get("replica_count", 1)
        desired_limits: dict[str, Any] = desired.get("resource_limits") or {}
        if isinstance(desired_limits, str):
            desired_limits = json.loads(desired_limits)

        desired_env_keys: list[str] = desired.get("env_var_keys") or []

        # Check image tags
        containers = live.spec.template.spec.containers or []
        live_images: dict[str, str] = {c.name: c.image for c in containers if c.image}

        for cname, desired_img in desired_images.items():
            live_img = live_images.get(cname, "")
            if live_img and live_img != desired_img:
                drifts.append({
                    "resource_type": "deployment",
                    "resource_name": name,
                    "namespace": namespace,
                    "drift_type": "image_tag_changed",
                    "old_value": {"container": cname, "image": desired_img},
                    "new_value": {"container": cname, "image": live_img},
                    "detected_at": now,
                })

        # Check replica count
        live_replicas = live.spec.replicas or 1
        if live_replicas != desired_replicas:
            drifts.append({
                "resource_type": "deployment",
                "resource_name": name,
                "namespace": namespace,
                "drift_type": "replica_count_changed",
                "old_value": {"replicas": desired_replicas},
                "new_value": {"replicas": live_replicas},
                "detected_at": now,
            })

        # Check env var keys
        live_env_keys: list[str] = []
        for c in containers:
            for env in (c.env or []):
                if env.name:
                    live_env_keys.append(env.name)

        added_keys = set(live_env_keys) - set(desired_env_keys)
        removed_keys = set(desired_env_keys) - set(live_env_keys)

        if added_keys:
            drifts.append({
                "resource_type": "deployment",
                "resource_name": name,
                "namespace": namespace,
                "drift_type": "env_vars_added",
                "old_value": {"keys": list(desired_env_keys)},
                "new_value": {"added": sorted(added_keys)},
                "detected_at": now,
            })

        if removed_keys:
            drifts.append({
                "resource_type": "deployment",
                "resource_name": name,
                "namespace": namespace,
                "drift_type": "env_vars_removed",
                "old_value": {"keys": list(desired_env_keys)},
                "new_value": {"removed": sorted(removed_keys)},
                "detected_at": now,
            })

        # Check resource limits
        for c in containers:
            cname = c.name
            desired_c_limits = desired_limits.get(cname, {})
            if not desired_c_limits:
                continue
            live_limits = {}
            live_requests = {}
            if c.resources:
                live_limits = dict(c.resources.limits or {})
                live_requests = dict(c.resources.requests or {})

            desired_limits_raw = desired_c_limits.get("limits", {})
            if str(live_limits) != str(desired_limits_raw):
                drifts.append({
                    "resource_type": "deployment",
                    "resource_name": name,
                    "namespace": namespace,
                    "drift_type": "resource_limits_changed",
                    "old_value": {"container": cname, "limits": desired_limits_raw},
                    "new_value": {"container": cname, "limits": live_limits},
                    "detected_at": now,
                })

        return drifts

    async def _record_drift_events(
        self,
        pool: Any,
        drifts: list[dict[str, Any]],
    ) -> None:
        """Insert drift events into the drift_events table."""
        async with pool.acquire() as conn:
            for drift in drifts:
                await conn.execute(
                    """
                    INSERT INTO drift_events (
                        resource_type, resource_name, namespace, drift_type,
                        old_value, new_value
                    ) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    drift["resource_type"],
                    drift["resource_name"],
                    drift["namespace"],
                    drift["drift_type"],
                    json.dumps(drift["old_value"]),
                    json.dumps(drift["new_value"]),
                )

    # ------------------------------------------------------------------
    # Auto-correction
    # ------------------------------------------------------------------

    async def auto_correct_drift(
        self,
        namespace: str,
        name: str,
        desired_state: dict[str, Any],
    ) -> bool:
        """Revert a deployment to the desired state snapshot."""
        logger.info(
            "Auto-correcting drift",
            deployment=name,
            namespace=namespace,
        )

        spec_snapshot = desired_state.get("spec_snapshot") or {}
        if isinstance(spec_snapshot, str):
            spec_snapshot = json.loads(spec_snapshot)

        if not spec_snapshot:
            logger.warning("No spec snapshot available for auto-correction", name=name)
            return False

        patch = {"spec": spec_snapshot}
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=patch
                ),
            )

            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE drift_events
                    SET auto_corrected = TRUE, corrected_at = NOW()
                    WHERE resource_name = $1 AND namespace = $2 AND auto_corrected = FALSE
                    """,
                    name,
                    namespace,
                )

            logger.info("Drift auto-corrected", deployment=name, namespace=namespace)
            return True
        except ApiException as exc:
            logger.error("Auto-correction failed", name=name, error=str(exc))
            return False
