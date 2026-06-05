"""GitHub integration — creates issues and comments on PRs."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubIntegration:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(self) -> None:
        if not settings.GITHUB_TOKEN:
            logger.warning("GITHUB_TOKEN is not set — GitHub integration will be limited")
        if not settings.GITHUB_REPO:
            logger.warning("GITHUB_REPO is not set — GitHub integration will be limited")

        self._headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._repo = settings.GITHUB_REPO  # "owner/repo"

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> str:
        """Create a GitHub issue and return its URL."""
        if not self._repo:
            raise ValueError("GITHUB_REPO is not configured")

        url = f"{GITHUB_API_BASE}/repos/{self._repo}/issues"
        payload: dict[str, Any] = {
            "title": title,
            "body": body,
            "labels": labels or [],
            "assignees": assignees or [],
        }

        async with httpx.AsyncClient(headers=self._headers, timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            issue_url: str = resp.json().get("html_url", "")
            logger.info("GitHub issue created", url=issue_url, title=title)
            return issue_url

    async def add_pr_comment(
        self,
        commit_sha: str,
        body: str,
    ) -> bool:
        """Find the PR for *commit_sha* and post a comment on it.

        Returns True if the comment was posted, False if no PR was found.
        """
        if not self._repo:
            raise ValueError("GITHUB_REPO is not configured")

        # Search for PRs associated with this commit
        url = f"{GITHUB_API_BASE}/repos/{self._repo}/commits/{commit_sha}/pulls"
        async with httpx.AsyncClient(
            headers={**self._headers, "Accept": "application/vnd.github.groot-preview+json"},
            timeout=15.0,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 404 or not resp.json():
                logger.debug("No PR found for commit", sha=commit_sha)
                return False

            prs = resp.json()
            if not prs:
                return False

            pr_number = prs[0].get("number")
            comment_url = f"{GITHUB_API_BASE}/repos/{self._repo}/issues/{pr_number}/comments"
            comment_resp = await client.post(comment_url, json={"body": body})
            comment_resp.raise_for_status()
            logger.info("PR comment posted", pr=pr_number, sha=commit_sha)
            return True

    async def update_commit_status(
        self,
        commit_sha: str,
        state: str,
        description: str,
        context: str = "autopilot/health-gate",
        target_url: str = "",
    ) -> None:
        """Update a commit status check (state: pending|success|failure|error)."""
        if not self._repo:
            return

        url = f"{GITHUB_API_BASE}/repos/{self._repo}/statuses/{commit_sha}"
        payload = {
            "state": state,
            "description": description[:140],
            "context": context,
        }
        if target_url:
            payload["target_url"] = target_url

        async with httpx.AsyncClient(headers=self._headers, timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Failed to update commit status",
                    sha=commit_sha,
                    state=state,
                    status_code=resp.status_code,
                )
            else:
                logger.info("Commit status updated", sha=commit_sha, state=state)
