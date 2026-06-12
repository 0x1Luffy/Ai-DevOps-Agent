"""Jenkins integration — webhook handling, build analysis, retry logic."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
import structlog

from config.prompts.jenkins_diagnosis import JENKINS_SYSTEM_PROMPT
from config.settings import settings
from core.llm import get_llm_client
from db.connection import get_pool
from db.repos.jenkins import (
    create_jenkins_incident,
    get_flaky_test_patterns,
    update_jenkins_incident,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Failure type → action matrix (mirrors JENKINS_SYSTEM_PROMPT logic)
# ---------------------------------------------------------------------------

RETRY_FAILURE_TYPES = {
    "FLAKY_TEST",
    "INFRASTRUCTURE_FAILURE",
    "TIMEOUT_FAILURE",
}

NO_RETRY_FAILURE_TYPES = {
    "REAL_TEST_FAILURE",
    "BUILD_FAILURE",
    "QUALITY_GATE_FAILURE",
    "SECURITY_SCAN_FAILURE",
    "PERMISSION_FAILURE",
}

CLEAN_WORKSPACE_TYPES = {
    "DEPENDENCY_FAILURE",
    "DOCKER_BUILD_FAILURE",
}


class JenkinsIntegration:
    """Handles Jenkins webhook events and build failure diagnosis."""

    def __init__(self) -> None:
        self._base_url = settings.JENKINS_URL.rstrip("/")
        self._user = settings.JENKINS_USER
        self._token = settings.JENKINS_TOKEN
        self._llm = get_llm_client()
        self._http: httpx.AsyncClient | None = None

    def _auth_header(self) -> str:
        creds = base64.b64encode(f"{self._user}:{self._token}".encode()).decode()
        return f"Basic {creds}"

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                headers={"Authorization": self._auth_header()},
                timeout=30.0,
            )
        return self._http

    # ------------------------------------------------------------------
    # Main webhook handler
    # ------------------------------------------------------------------

    async def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process a Jenkins webhook payload."""
        build = payload.get("build", {})
        job_name: str = payload.get("name", build.get("full_display_name", "unknown"))
        build_number: int = build.get("number", 0)
        build_phase: str = build.get("phase", "").upper()
        build_status: str = build.get("status", "").upper()
        branch: str = build.get("scm", {}).get("branch", "")
        commit_sha: str = build.get("scm", {}).get("commit", "")
        duration_sec: int = build.get("duration", 0) // 1000

        logger.info(
            "Jenkins webhook received",
            job=job_name,
            build=build_number,
            phase=build_phase,
            status=build_status,
        )

        if build_phase == "COMPLETED" and build_status == "SUCCESS":
            # Trigger post-deploy health checker asynchronously
            asyncio.ensure_future(
                self.post_deploy_health_checker(job_name, build_number)
            )
            return {"action": "health_check_scheduled"}

        if build_phase == "COMPLETED" and build_status in ("FAILURE", "ABORTED", "UNSTABLE"):
            console_log = await self.fetch_console_log(job_name, build_number)
            build_info = await self.fetch_build_info(job_name, build_number)

            diagnosis = await self.diagnose_build_failure(
                job_name, build_number, console_log, branch, commit_sha, build_info
            )

            pool = await get_pool()
            incident_id = await create_jenkins_incident(
                pool,
                {
                    "job_name": job_name,
                    "build_number": build_number,
                    "branch": branch,
                    "commit_sha": commit_sha,
                    "failure_type": diagnosis.get("failureType", "UNKNOWN"),
                    "failing_stage": diagnosis.get("failingStage"),
                    "failing_line": diagnosis.get("failingLine"),
                    "ai_diagnosis": diagnosis,
                    "action_taken": diagnosis.get("action", "notify_team"),
                    "build_duration_seconds": duration_sec,
                    "console_log_snippet": console_log[:2000] if console_log else "",
                },
            )

            return await self._execute_action(
                incident_id, job_name, build_number, diagnosis, branch, commit_sha
            )

        return {"action": "ignored", "phase": build_phase, "status": build_status}

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        incident_id: str,
        job_name: str,
        build_number: int,
        diagnosis: dict[str, Any],
        branch: str,
        commit_sha: str,
    ) -> dict[str, Any]:
        action = diagnosis.get("action", "notify_team")
        failure_type = diagnosis.get("failureType", "UNKNOWN")
        retry_build = diagnosis.get("retryBuild", False)
        clean_workspace = diagnosis.get("cleanWorkspace", False)

        # Check retry count limit
        pool = await get_pool()
        patterns = await get_flaky_test_patterns(pool, job_name)
        retry_count = len([p for p in patterns if p.get("occurrence_count", 0) >= settings.JENKINS_MAX_RETRIES])

        result: dict[str, Any] = {
            "incident_id": incident_id,
            "action": action,
            "failure_type": failure_type,
        }

        if action == "retry_build" and retry_build:
            if retry_count < settings.JENKINS_MAX_RETRIES:
                try:
                    crumb = await self.get_crumb()
                    retried = await self.retry_build(
                        job_name, build_number, crumb, clean_workspace=clean_workspace
                    )
                    result["retried"] = retried
                    if retried:
                        await update_jenkins_incident(
                            pool,
                            incident_id,
                            action_taken="retry_build",
                            retry_count=1,
                        )
                except Exception as exc:
                    logger.error("Retry failed", error=str(exc))
                    result["retry_error"] = str(exc)
            else:
                logger.warning(
                    "Max retries reached for job",
                    job=job_name,
                    max=settings.JENKINS_MAX_RETRIES,
                )
                result["skipped_retry"] = "max_retries_reached"

        elif action == "create_github_issue":
            title = diagnosis.get("githubIssueTitle", f"[{failure_type}] {job_name} build {build_number} failed")
            body = diagnosis.get("githubIssueBody", "")
            if not body:
                body = self._build_github_issue_body(diagnosis, job_name, build_number, branch, commit_sha)
            try:
                from integrations.github import GitHubIntegration
                gh = GitHubIntegration()
                issue_url = await gh.create_issue(
                    title=title,
                    body=body,
                    labels=["ci-failure", failure_type.lower().replace("_", "-")],
                )
                result["github_issue_url"] = issue_url
                await update_jenkins_incident(
                    pool,
                    incident_id,
                    action_taken="create_github_issue",
                    github_issue_url=issue_url,
                )
            except Exception as exc:
                logger.error("GitHub issue creation failed", error=str(exc))
                result["github_error"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # Console log & build info
    # ------------------------------------------------------------------

    async def fetch_console_log(self, job_name: str, build_number: int) -> str:
        """Fetch and truncate the Jenkins build console log to 300 lines."""
        url = f"{self._base_url}/job/{_encode_job_name(job_name)}/{build_number}/consoleText"
        http = await self._get_http()
        try:
            resp = await http.get(url)
            resp.raise_for_status()
            lines = resp.text.splitlines()
            return "\n".join(lines[-300:])
        except httpx.HTTPStatusError as exc:
            logger.warning("Failed to fetch console log", job=job_name, error=str(exc))
            return ""
        except Exception as exc:
            logger.warning("Console log fetch error", error=str(exc))
            return ""

    async def fetch_build_info(self, job_name: str, build_number: int) -> dict[str, Any]:
        """Fetch JSON build metadata from Jenkins API."""
        url = f"{self._base_url}/job/{_encode_job_name(job_name)}/{build_number}/api/json"
        http = await self._get_http()
        try:
            resp = await http.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch build info", job=job_name, error=str(exc))
            return {}

    async def get_crumb(self) -> str:
        """Fetch a Jenkins CSRF crumb for use in POST requests."""
        url = f"{self._base_url}/crumbIssuer/api/json"
        http = await self._get_http()
        try:
            resp = await http.get(url)
            resp.raise_for_status()
            data = resp.json()
            return f"{data.get('crumbRequestField', 'Jenkins-Crumb')}:{data.get('crumb', '')}"
        except Exception as exc:
            logger.warning("Failed to get Jenkins crumb", error=str(exc))
            return ""

    # ------------------------------------------------------------------
    # Retry build
    # ------------------------------------------------------------------

    async def retry_build(
        self,
        job_name: str,
        build_number: int,
        crumb: str,
        clean_workspace: bool = False,
    ) -> bool:
        """Trigger a new build for the given job."""
        if clean_workspace:
            # Trigger clean-workspace build via wipeWorkspace action
            url = f"{self._base_url}/job/{_encode_job_name(job_name)}/{build_number}/doWipeOutWorkspace"
            http = await self._get_http()
            try:
                crumb_header, crumb_value = crumb.split(":", 1) if ":" in crumb else ("Jenkins-Crumb", crumb)
                await http.post(url, headers={crumb_header: crumb_value})
            except Exception:
                pass

        url = f"{self._base_url}/job/{_encode_job_name(job_name)}/build"
        http = await self._get_http()
        try:
            crumb_header, crumb_value = crumb.split(":", 1) if ":" in crumb else ("Jenkins-Crumb", crumb)
            resp = await http.post(url, headers={crumb_header: crumb_value})
            success = resp.status_code in (200, 201, 302)
            if success:
                logger.info("Retry build triggered", job=job_name, clean=clean_workspace)
            else:
                logger.warning("Retry build returned non-2xx", status=resp.status_code)
            return success
        except Exception as exc:
            logger.error("Retry build failed", job=job_name, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # AI diagnosis
    # ------------------------------------------------------------------

    async def diagnose_build_failure(
        self,
        job_name: str,
        build_number: int,
        console_log: str,
        branch: str = "",
        commit_sha: str = "",
        build_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send build failure data to the active LLM provider for diagnosis."""
        trend = await self.analyze_build_trend(job_name)
        recent_failures = trend.get("recent_failures", [])

        prompt_lines = [
            "JENKINS BUILD FAILURE REPORT",
            "============================",
            f"Job Name     : {job_name}",
            f"Build Number : {build_number}",
            f"Branch       : {branch}",
            f"Commit SHA   : {commit_sha}",
            "",
        ]

        if build_info:
            duration = build_info.get("duration", 0) // 1000
            prompt_lines.append(f"Build Duration: {duration}s")
            prompt_lines.append(f"Result: {build_info.get('result', 'unknown')}")
            prompt_lines.append("")

        if recent_failures:
            prompt_lines.append(f"Recent failure types (last 5 builds): {recent_failures}")
            prompt_lines.append("")

        if console_log:
            prompt_lines.append("--- Console Log (last 300 lines) ---")
            prompt_lines.append(console_log[-6000:])

        prompt = "\n".join(prompt_lines)

        try:
            raw = await self._llm.complete(
                system=JENKINS_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=2048,
                json_mode=True,
            )
            return json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse Jenkins diagnosis JSON", error=str(exc))
            return {"failureType": "UNKNOWN", "action": "notify_team", "retryBuild": False}
        except Exception as exc:
            logger.error("Jenkins diagnosis API error", error=str(exc))
            return {"failureType": "UNKNOWN", "action": "notify_team", "retryBuild": False}

    # ------------------------------------------------------------------
    # Post-deploy health checker
    # ------------------------------------------------------------------

    async def post_deploy_health_checker(self, job_name: str, build_number: int) -> None:
        """Run 2 minutes after a successful deploy to verify cluster health."""
        import asyncio as _asyncio
        await _asyncio.sleep(120)
        logger.info("Running post-deploy health check", job=job_name, build=build_number)

        from core.scanner import ClusterScanner
        scanner = ClusterScanner()
        # Run a quick scan on the primary deployment namespace
        for ns in settings.target_namespaces_list:
            incidents = scanner.scan_deployments(ns)
            if incidents:
                logger.warning(
                    "Post-deploy health issues detected",
                    job=job_name,
                    build=build_number,
                    count=len(incidents),
                    namespace=ns,
                )
                # Publish to Redis
                import redis.asyncio as aioredis
                redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                try:
                    await redis_client.publish(
                        "autopilot:events",
                        json.dumps({
                            "event": "post_deploy_health_issue",
                            "job_name": job_name,
                            "build_number": build_number,
                            "namespace": ns,
                            "issue_count": len(incidents),
                        }),
                    )
                finally:
                    await redis_client.aclose()

    # ------------------------------------------------------------------
    # Build trend analysis
    # ------------------------------------------------------------------

    async def analyze_build_trend(self, job_name: str) -> dict[str, Any]:
        """Analyse recent build failures to detect patterns."""
        pool = await get_pool()
        patterns = await get_flaky_test_patterns(pool, job_name)

        url = f"{self._base_url}/job/{_encode_job_name(job_name)}/api/json?tree=builds[number,result,duration]{{0,10}}"
        http = await self._get_http()
        recent_failures: list[str] = []

        try:
            resp = await http.get(url)
            resp.raise_for_status()
            builds = resp.json().get("builds", [])
            recent_failures = [
                b.get("result", "")
                for b in builds
                if b.get("result") in ("FAILURE", "UNSTABLE", "ABORTED")
            ]
        except Exception:
            pass

        return {
            "job_name": job_name,
            "flaky_patterns": patterns,
            "recent_failures": recent_failures[:5],
            "failure_rate": round(len(recent_failures) / max(1, 10) * 100, 1),
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _build_github_issue_body(
        diagnosis: dict[str, Any],
        job_name: str,
        build_number: int,
        branch: str,
        commit_sha: str,
    ) -> str:
        lines = [
            f"## CI Failure: {job_name} #{build_number}",
            "",
            f"**Branch:** `{branch}`",
            f"**Commit:** `{commit_sha}`",
            f"**Failure Type:** {diagnosis.get('failureType', 'unknown')}",
            f"**Failing Stage:** {diagnosis.get('failingStage', 'unknown')}",
            "",
            "## Root Cause",
            diagnosis.get("rootCause", "See console log"),
            "",
            "## Fix Suggestion",
            diagnosis.get("fixSuggestion", ""),
            "",
            "## Prevention",
            diagnosis.get("preventionTip", ""),
            "",
            "---",
            "_Created automatically by AutoPilot DevOps Agent_",
        ]
        return "\n".join(lines)


def _encode_job_name(job_name: str) -> str:
    """Convert job name with slashes to the Jenkins /job/X/job/Y URL format."""
    parts = job_name.split("/")
    return "/job/".join(parts)
