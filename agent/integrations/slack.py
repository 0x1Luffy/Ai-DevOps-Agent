"""Slack integration — alerts, approval flows, and bot command handling."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import structlog
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config.settings import runtime_config, settings
from db.connection import get_pool
from db.repos.incidents import get_incident, list_incidents, update_incident_status

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Severity helper
# ---------------------------------------------------------------------------

SEVERITY_EMOJI = {
    "LOW": ":information_source:",
    "MEDIUM": ":warning:",
    "HIGH": ":rotating_light:",
    "CRITICAL": ":sos:",
}

STATUS_EMOJI = {
    "open": ":white_circle:",
    "diagnosing": ":mag:",
    "needs_approval": ":hourglass_flowing_sand:",
    "fixing": ":wrench:",
    "fixed": ":white_check_mark:",
    "still_broken": ":x:",
    "escalated": ":mega:",
    "manual": ":hand:",
    "skipped": ":next_track_button:",
}


# ---------------------------------------------------------------------------
# SlackIntegration
# ---------------------------------------------------------------------------


class SlackIntegration:
    """Manages all Slack interactions for AutoPilot."""

    def __init__(self) -> None:
        self.app = App(
            token=settings.SLACK_BOT_TOKEN,
            signing_secret=settings.SLACK_SIGNING_SECRET,
        )
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
        self._register_handlers()

    # ------------------------------------------------------------------
    # Alert / notification methods
    # ------------------------------------------------------------------

    def send_alert(
        self,
        incident: dict[str, Any],
        diagnosis: dict[str, Any] | None = None,
    ) -> str | None:
        """Send an informational alert to SLACK_ALERT_CHANNEL.

        Returns the message timestamp for later updates.
        """
        severity = incident.get("severity", "MEDIUM")
        emoji = SEVERITY_EMOJI.get(severity, ":warning:")
        namespace = incident.get("namespace", "unknown")
        resource = incident.get("resource_name", "unknown")
        problem = incident.get("problem_type", "unknown")
        incident_id = incident.get("id", "")

        root_cause = ""
        confidence = 0
        fix_count = 0
        if diagnosis:
            root_cause = diagnosis.get("root_cause", "")
            confidence = diagnosis.get("confidence", 0)
            fix_count = len(diagnosis.get("fix_plan", []))

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} [{severity}] {problem} — {resource}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Namespace:*\n`{namespace}`"},
                    {"type": "mrkdwn", "text": f"*Resource:*\n`{resource}`"},
                    {"type": "mrkdwn", "text": f"*Problem:*\n{problem}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence}%"},
                ],
            },
        ]

        if root_cause:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{root_cause}"},
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Incident ID: `{incident_id}` | Fix steps: {fix_count}",
                }
            ],
        })

        try:
            resp = self.client.chat_postMessage(
                channel=settings.SLACK_ALERT_CHANNEL,
                blocks=blocks,
                text=f"[{severity}] {problem} in {namespace}/{resource}",
            )
            return resp["ts"]
        except SlackApiError as exc:
            logger.error("Slack alert failed", error=str(exc))
            return None

    def send_approval_request(
        self,
        incident: dict[str, Any],
        diagnosis: dict[str, Any],
    ) -> tuple[str | None, str]:
        """Send an approval Block Kit message to SLACK_APPROVAL_CHANNEL.

        Returns (message_ts, channel).
        """
        severity = incident.get("severity", "CRITICAL")
        emoji = SEVERITY_EMOJI.get(severity, ":sos:")
        namespace = incident.get("namespace", "unknown")
        resource = incident.get("resource_name", "unknown")
        problem = incident.get("problem_type", "unknown")
        incident_id = str(incident.get("id", ""))
        root_cause = diagnosis.get("root_cause", "")
        confidence = diagnosis.get("confidence", 0)
        fix_plan = diagnosis.get("fix_plan", [])
        estimated_recovery = diagnosis.get("estimated_recovery", "unknown")
        prevention_tip = diagnosis.get("prevention_tip", "")

        fix_summary_lines = []
        for i, step in enumerate(fix_plan[:5], 1):
            desc = step.get("description", step.get("action", ""))
            cmd = step.get("kubectl_equivalent", "")
            fix_summary_lines.append(f"{i}. {desc}")
            if cmd:
                fix_summary_lines.append(f"   `{cmd}`")

        fix_summary = "\n".join(fix_summary_lines) or "_No fix steps_"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Approval Required — {severity} Incident",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Namespace:*\n`{namespace}`"},
                    {"type": "mrkdwn", "text": f"*Resource:*\n`{resource}`"},
                    {"type": "mrkdwn", "text": f"*Problem:*\n{problem}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence}%"},
                    {"type": "mrkdwn", "text": f"*Est. Recovery:*\n{estimated_recovery}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{root_cause}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Proposed Fix Plan:*\n{fix_summary}"},
            },
        ]

        if prevention_tip:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":bulb: *Prevention:* {prevention_tip}"}
                ],
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "block_id": f"approval_{incident_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve Fix"},
                    "style": "primary",
                    "action_id": "approve_fix",
                    "value": incident_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Confirm Fix"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Apply {len(fix_plan)} fix step(s) to `{resource}` in `{namespace}`?",
                        },
                        "confirm": {"type": "plain_text", "text": "Yes, apply fix"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Skip"},
                    "style": "danger",
                    "action_id": "skip_fix",
                    "value": incident_id,
                },
            ],
        })

        try:
            resp = self.client.chat_postMessage(
                channel=settings.SLACK_APPROVAL_CHANNEL,
                blocks=blocks,
                text=f"[APPROVAL NEEDED] {problem} on {namespace}/{resource}",
            )
            ts = resp["ts"]
            channel = resp["channel"]
            logger.info("Approval request sent", incident_id=incident_id, ts=ts)
            return ts, channel
        except SlackApiError as exc:
            logger.error("Failed to send approval request", error=str(exc))
            return None, settings.SLACK_APPROVAL_CHANNEL

    def update_approval_message(
        self,
        ts: str,
        channel: str,
        status: str,
        approver: str = "",
    ) -> None:
        """Replace the approval buttons with a status badge."""
        emoji = ":white_check_mark:" if status == "approved" else ":no_entry_sign:"
        actor = f" by <@{approver}>" if approver else ""
        text = f"{emoji} Fix *{status}*{actor}"

        try:
            self.client.chat_update(
                channel=channel,
                ts=ts,
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": text},
                    }
                ],
                text=text,
            )
        except SlackApiError as exc:
            logger.warning("Failed to update approval message", error=str(exc))

    # ------------------------------------------------------------------
    # Action handlers (Block Kit buttons)
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        app = self.app

        @app.action("approve_fix")
        def handle_approve_fix(ack: Any, body: dict[str, Any], client: WebClient) -> None:
            ack()
            incident_id = body.get("actions", [{}])[0].get("value", "")
            user_id = body.get("user", {}).get("id", "")
            channel = body.get("channel", {}).get("id", settings.SLACK_APPROVAL_CHANNEL)
            ts = body.get("message", {}).get("ts", "")

            logger.info("Fix approved via Slack", incident_id=incident_id, approver=user_id)
            self.update_approval_message(ts, channel, "approved", approver=user_id)

            # Run the executor in a new event loop (Slack handlers are sync)
            asyncio.run(self._execute_approved_fix(incident_id, user_id))

        @app.action("skip_fix")
        def handle_skip_fix(ack: Any, body: dict[str, Any], client: WebClient) -> None:
            ack()
            incident_id = body.get("actions", [{}])[0].get("value", "")
            user_id = body.get("user", {}).get("id", "")
            channel = body.get("channel", {}).get("id", settings.SLACK_APPROVAL_CHANNEL)
            ts = body.get("message", {}).get("ts", "")

            logger.info("Fix skipped via Slack", incident_id=incident_id, skipped_by=user_id)
            self.update_approval_message(ts, channel, "skipped", approver=user_id)

            asyncio.run(self._skip_incident(incident_id))

        @app.event("app_mention")
        def handle_mention(event: dict[str, Any], say: Any) -> None:
            text: str = event.get("text", "").lower()
            parts = text.split()
            # Remove the bot mention token (@botname)
            cmd_parts = [p for p in parts if not p.startswith("<@")]

            if not cmd_parts:
                say(self._help_text())
                return

            cmd = cmd_parts[0] if cmd_parts else ""

            if cmd == "help":
                say(self._help_text())

            elif cmd == "status":
                namespace_filter = cmd_parts[1] if len(cmd_parts) > 1 else None
                asyncio.run(self._handle_status(say, namespace_filter))

            elif cmd == "rollback" and len(cmd_parts) > 1:
                service_name = cmd_parts[1]
                asyncio.run(self._handle_rollback(say, service_name))

            elif cmd == "logs" and len(cmd_parts) > 1:
                pod_name = cmd_parts[1]
                asyncio.run(self._handle_logs(say, pod_name))

            elif cmd == "incidents" and len(cmd_parts) > 1 and cmd_parts[1] == "today":
                asyncio.run(self._handle_incidents_today(say))

            elif cmd == "approve" and len(cmd_parts) > 1:
                incident_id = cmd_parts[1]
                user_id = event.get("user", "")
                asyncio.run(self._execute_approved_fix(incident_id, user_id))
                say(f":white_check_mark: Executing fix for incident `{incident_id}`")

            elif cmd == "dry-run" and len(cmd_parts) > 1:
                mode = cmd_parts[1]
                if mode == "on":
                    runtime_config["DRY_RUN"] = True
                    say(":eyes: Dry-run mode *enabled* — no changes will be applied")
                elif mode == "off":
                    runtime_config["DRY_RUN"] = False
                    say(":zap: Dry-run mode *disabled* — fixes will be applied")
                else:
                    say("Usage: `dry-run on` or `dry-run off`")

            else:
                say(self._help_text())

    # ------------------------------------------------------------------
    # Async helpers called from sync Slack handlers
    # ------------------------------------------------------------------

    async def _execute_approved_fix(self, incident_id: str, approver_slack_id: str) -> None:
        from core.executor import FixExecutor
        pool = await get_pool()
        incident = await get_incident(pool, incident_id)
        if not incident:
            logger.warning("Incident not found for approval", incident_id=incident_id)
            return

        fix_plan = incident.get("fix_plan") or []
        if isinstance(fix_plan, str):
            fix_plan = json.loads(fix_plan)

        executor = FixExecutor()
        await executor.execute_fix_plan(incident_id, fix_plan, approver_slack_id=approver_slack_id)

    async def _skip_incident(self, incident_id: str) -> None:
        pool = await get_pool()
        await update_incident_status(pool, incident_id, "skipped")

    async def _handle_status(self, say: Any, namespace: str | None) -> None:
        from db.repos.incidents import get_incident_stats
        pool = await get_pool()
        stats = await get_incident_stats(pool)
        lines = [
            "*:bar_chart: AutoPilot Status*",
            f"Open incidents: *{stats.get('open_count', 0)}*",
            f"Critical open: *{stats.get('critical_open', 0)}*",
            f"Fixed last 24h: *{stats.get('fixed_24h', 0)}*",
        ]
        if namespace:
            filters: dict[str, Any] = {"namespace": namespace}
            rows, total = await list_incidents(pool, filters, page=1, limit=5)
            lines.append(f"\nRecent incidents in `{namespace}` ({total} total):")
            for inc in rows:
                em = STATUS_EMOJI.get(inc.get("status", ""), ":white_circle:")
                lines.append(f"  {em} [{inc['severity']}] {inc['problem_type']} — `{inc['resource_name']}`")
        say("\n".join(lines))

    async def _handle_rollback(self, say: Any, service_name: str) -> None:
        from core.executor import FixExecutor
        executor = FixExecutor()
        # Find the namespace for this service across target namespaces
        from config.settings import settings
        from kubernetes import client as k8s_client
        try:
            for ns in settings.target_namespaces_list:
                fix_params = {"namespace": ns, "name": service_name}
                result = await executor.rollout_undo(fix_params, "slack-triggered")
                if result.success:
                    say(f":arrows_counterclockwise: Rollback triggered for `{service_name}` in `{ns}`")
                    return
        except Exception as exc:
            say(f":x: Rollback failed: {exc}")

    async def _handle_logs(self, say: Any, pod_name: str) -> None:
        from core.scanner import ClusterScanner
        scanner = ClusterScanner()
        for ns in settings.target_namespaces_list:
            ctx = scanner.collect_pod_context(ns, pod_name)
            if ctx.get("logs") and ctx["logs"] != "unavailable":
                log_snippet = str(ctx["logs"])[-1500:]
                say(f":scroll: Logs for `{pod_name}` in `{ns}`:\n```{log_snippet}```")
                return
        say(f":x: Could not retrieve logs for `{pod_name}`")

    async def _handle_incidents_today(self, say: Any) -> None:
        from datetime import datetime, timezone, timedelta
        pool = await get_pool()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        rows, total = await list_incidents(pool, {"since": since}, page=1, limit=20)
        if not rows:
            say(":white_check_mark: No incidents in the last 24 hours!")
            return
        lines = [f"*:rotating_light: {total} incident(s) in the last 24h:*"]
        for inc in rows:
            em = STATUS_EMOJI.get(inc.get("status", ""), ":white_circle:")
            lines.append(
                f"  {em} `{inc['id'][:8]}` [{inc['severity']}] {inc['problem_type']} "
                f"— `{inc['namespace']}/{inc['resource_name']}`"
            )
        say("\n".join(lines))

    @staticmethod
    def _help_text() -> str:
        return (
            "*AutoPilot DevOps Agent* — available commands:\n"
            "• `status` — overall cluster health\n"
            "• `status {namespace}` — incidents in a namespace\n"
            "• `rollback {service}` — rollback a deployment\n"
            "• `logs {pod-name}` — fetch recent pod logs\n"
            "• `incidents today` — incidents in the last 24h\n"
            "• `approve {incident-id}` — manually approve a fix\n"
            "• `dry-run on|off` — toggle dry-run mode\n"
            "• `help` — show this message"
        )

    # ------------------------------------------------------------------
    # Start the bot in a background daemon thread
    # ------------------------------------------------------------------

    def start_background(self, app_token: str | None = None) -> threading.Thread:
        """Start the Slack Bolt SocketMode handler in a daemon thread."""
        def _run() -> None:
            try:
                handler = SocketModeHandler(self.app, app_token or settings.SLACK_BOT_TOKEN)
                handler.start()
            except Exception as exc:
                logger.error("Slack SocketMode handler failed", error=str(exc))

        thread = threading.Thread(target=_run, daemon=True, name="slack-bolt")
        thread.start()
        logger.info("Slack Bolt started in background thread")
        return thread
