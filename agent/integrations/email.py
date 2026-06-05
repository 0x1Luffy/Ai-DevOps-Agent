"""Email integration — SMTP escalation emails for critical incidents."""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


class EmailIntegration:
    """Sends escalation emails over SMTP with STARTTLS."""

    def __init__(self) -> None:
        self._host = settings.SMTP_HOST
        self._port = settings.SMTP_PORT
        self._user = settings.SMTP_USER
        self._password = settings.SMTP_PASS
        self._escalation_to = settings.ESCALATION_EMAIL

    async def send_escalation_email(
        self,
        subject: str,
        body: str,
        incident: dict[str, Any] | None = None,
    ) -> bool:
        """Send an HTML escalation email.

        Runs the blocking SMTP call in a thread-pool executor so it doesn't
        block the event loop.
        """
        if not self._escalation_to:
            logger.warning("ESCALATION_EMAIL is not configured — skipping email")
            return False

        html_body = self._build_html(subject, body, incident)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._send_sync,
            subject,
            html_body,
        )

    def _send_sync(self, subject: str, html_body: str) -> bool:
        """Blocking SMTP send (run in executor)."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._user or f"autopilot@{self._host}"
        msg["To"] = self._escalation_to

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self._host, self._port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if self._user and self._password:
                    smtp.login(self._user, self._password)
                smtp.sendmail(msg["From"], [self._escalation_to], msg.as_string())
            logger.info("Escalation email sent", to=self._escalation_to, subject=subject)
            return True
        except smtplib.SMTPException as exc:
            logger.error("SMTP error sending escalation email", error=str(exc))
            return False
        except OSError as exc:
            logger.error("Network error sending escalation email", error=str(exc))
            return False

    @staticmethod
    def _build_html(
        subject: str,
        body: str,
        incident: dict[str, Any] | None,
    ) -> str:
        """Render a minimal but readable HTML email."""
        severity = incident.get("severity", "UNKNOWN") if incident else "UNKNOWN"
        namespace = incident.get("namespace", "unknown") if incident else "unknown"
        resource = incident.get("resource_name", "unknown") if incident else "unknown"
        problem = incident.get("problem_type", "unknown") if incident else "unknown"
        root_cause = incident.get("root_cause", "") if incident else ""
        incident_id = str(incident.get("id", "")) if incident else ""

        severity_color = {
            "LOW": "#17a2b8",
            "MEDIUM": "#ffc107",
            "HIGH": "#fd7e14",
            "CRITICAL": "#dc3545",
        }.get(severity, "#6c757d")

        rows = ""
        if incident:
            fields = [
                ("Incident ID", f"<code>{incident_id}</code>"),
                ("Namespace", f"<code>{namespace}</code>"),
                ("Resource", f"<code>{resource}</code>"),
                ("Problem Type", problem),
                ("Severity", f'<span style="color:{severity_color};font-weight:bold">{severity}</span>'),
            ]
            if root_cause:
                fields.append(("Root Cause", root_cause))
            rows = "".join(
                f"<tr><td style='padding:8px;font-weight:bold;background:#f8f9fa'>{k}</td>"
                f"<td style='padding:8px'>{v}</td></tr>"
                for k, v in fields
            )

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f6f8">
  <div style="max-width:640px;margin:32px auto;background:#ffffff;border-radius:8px;
              box-shadow:0 2px 8px rgba(0,0,0,0.1);overflow:hidden">
    <div style="background:{severity_color};color:#fff;padding:20px 24px">
      <h2 style="margin:0">&#x1F6A8; AutoPilot Escalation — {severity}</h2>
      <p style="margin:4px 0 0">{subject}</p>
    </div>
    <div style="padding:24px">
      {"<table style='border-collapse:collapse;width:100%'>" + rows + "</table>" if rows else ""}
      <div style="margin-top:20px;padding:16px;background:#f8f9fa;border-radius:4px;
                  font-family:monospace;white-space:pre-wrap;font-size:13px">{body}</div>
    </div>
    <div style="padding:12px 24px;background:#f4f6f8;font-size:12px;color:#6c757d">
      This message was sent automatically by AutoPilot DevOps Agent.
    </div>
  </div>
</body>
</html>"""
        return html
