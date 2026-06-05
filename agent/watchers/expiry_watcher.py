"""ExpiryWatcher — monitors TLS certificate and secret expiry."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from config.settings import settings

logger = structlog.get_logger(__name__)

EXPIRY_ANNOTATION = "autopilot.io/expiry-date"
WARNING_DAYS = 30
CRITICAL_DAYS = 7


class ExpiryWatcher:
    """Scans TLS secrets and annotated secrets for upcoming expiry."""

    def __init__(self) -> None:
        if settings.K8S_IN_CLUSTER:
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config(config_file=settings.KUBECONFIG)

        self.core_v1 = k8s_client.CoreV1Api()

    async def check_tls_certs(self) -> list[dict[str, Any]]:
        """Scan all TLS secrets across target namespaces and alert on near-expiry."""
        alerts: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for namespace in settings.target_namespaces_list:
            try:
                # Scan TLS secrets
                secrets = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self.core_v1.list_namespaced_secret(
                        namespace=ns, field_selector="type=kubernetes.io/tls"
                    ),
                )
                for secret in secrets.items:
                    alert = self._check_tls_secret(secret, namespace, now)
                    if alert:
                        alerts.append(alert)
                        await self._handle_alert(alert)

                # Scan secrets with expiry annotation
                annotated = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ns=namespace: self.core_v1.list_namespaced_secret(namespace=ns),
                )
                for secret in annotated.items:
                    annotations = secret.metadata.annotations or {}
                    expiry_str = annotations.get(EXPIRY_ANNOTATION)
                    if expiry_str:
                        alert = self._check_annotated_secret(secret, namespace, expiry_str, now)
                        if alert:
                            alerts.append(alert)
                            await self._handle_alert(alert)

            except ApiException as exc:
                logger.warning("Cannot list secrets", namespace=namespace, error=str(exc))
            except Exception as exc:
                logger.warning("Expiry check error", namespace=namespace, error=str(exc))

        if alerts:
            logger.warning("TLS certificate expiry alerts", count=len(alerts))
        else:
            logger.info("TLS certificate check complete — no alerts")

        return alerts

    def _check_tls_secret(
        self,
        secret: Any,
        namespace: str,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Parse the tls.crt field of a TLS secret and check expiry."""
        secret_name = secret.metadata.name
        data = secret.data or {}
        tls_crt = data.get("tls.crt")
        if not tls_crt:
            return None

        try:
            cert_bytes = base64.b64decode(tls_crt)
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
            not_after = cert.not_valid_after_utc
        except Exception as exc:
            logger.debug("Cannot parse TLS cert", secret=secret_name, error=str(exc))
            return None

        days_remaining = (not_after - now).days
        if days_remaining > WARNING_DAYS:
            return None

        severity = "CRITICAL" if days_remaining <= CRITICAL_DAYS else "WARNING"
        subject = cert.subject.rfc4514_string() if cert.subject else ""

        logger.warning(
            "TLS certificate expiry alert",
            secret=secret_name,
            namespace=namespace,
            days_remaining=days_remaining,
            severity=severity,
            subject=subject,
        )

        return {
            "type": "tls_cert",
            "secret_name": secret_name,
            "namespace": namespace,
            "not_after": not_after.isoformat(),
            "days_remaining": days_remaining,
            "severity": severity,
            "subject": subject,
        }

    def _check_annotated_secret(
        self,
        secret: Any,
        namespace: str,
        expiry_str: str,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Check a secret annotated with autopilot.io/expiry-date."""
        secret_name = secret.metadata.name
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            logger.debug(
                "Cannot parse expiry annotation",
                secret=secret_name,
                annotation=expiry_str,
                error=str(exc),
            )
            return None

        days_remaining = (expiry - now).days
        if days_remaining > WARNING_DAYS:
            return None

        severity = "CRITICAL" if days_remaining <= CRITICAL_DAYS else "WARNING"
        logger.warning(
            "Annotated secret expiry alert",
            secret=secret_name,
            namespace=namespace,
            days_remaining=days_remaining,
            severity=severity,
        )

        return {
            "type": "annotated_secret",
            "secret_name": secret_name,
            "namespace": namespace,
            "not_after": expiry.isoformat(),
            "days_remaining": days_remaining,
            "severity": severity,
        }

    async def _handle_alert(self, alert: dict[str, Any]) -> None:
        """Send Slack alert and escalation email for expiry warnings."""
        secret_name = alert["secret_name"]
        namespace = alert["namespace"]
        days = alert["days_remaining"]
        severity = alert["severity"]

        try:
            from integrations.slack import SlackIntegration
            slack = SlackIntegration()
            slack.send_alert(
                incident={
                    "severity": severity,
                    "namespace": namespace,
                    "resource_name": secret_name,
                    "problem_type": "CertificateExpiry",
                    "id": f"expiry-{secret_name}",
                },
                diagnosis={
                    "root_cause": f"TLS certificate/secret `{secret_name}` expires in {days} day(s)",
                    "confidence": 100,
                    "fix_plan": [],
                    "estimated_recovery": "Renew certificate",
                },
            )
        except Exception as exc:
            logger.warning("Failed to send Slack expiry alert", error=str(exc))

        # Email for CRITICAL (<=7 days)
        if severity == "CRITICAL":
            try:
                from integrations.email import EmailIntegration
                email = EmailIntegration()
                await email.send_escalation_email(
                    subject=f"[CRITICAL] Certificate expires in {days} days: {namespace}/{secret_name}",
                    body=(
                        f"Secret: {secret_name}\n"
                        f"Namespace: {namespace}\n"
                        f"Expires: {alert.get('not_after', 'unknown')}\n"
                        f"Days remaining: {days}\n\n"
                        "Please renew the certificate immediately."
                    ),
                    incident={
                        "severity": "CRITICAL",
                        "namespace": namespace,
                        "resource_name": secret_name,
                        "problem_type": "CertificateExpiry",
                        "id": f"expiry-{secret_name}",
                    },
                )
            except Exception as exc:
                logger.warning("Failed to send expiry escalation email", error=str(exc))
