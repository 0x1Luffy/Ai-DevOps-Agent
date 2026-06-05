"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Kubernetes
    K8S_IN_CLUSTER: bool = True
    KUBECONFIG: str = "/root/.kube/config"
    TARGET_NAMESPACES: str = "default,production,staging"

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    AI_CONFIDENCE_THRESHOLD: int = 85

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Jenkins
    JENKINS_URL: str = "http://jenkins.jenkins.svc.cluster.local:8080"
    JENKINS_USER: str = "admin"
    JENKINS_TOKEN: str = ""
    JENKINS_WEBHOOK_SECRET: str = ""
    JENKINS_MAX_RETRIES: int = 2

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_ALERT_CHANNEL: str = "#devops-alerts"
    SLACK_APPROVAL_CHANNEL: str = "#devops-approvals"
    SLACK_APPROVAL_TIMEOUT_MINUTES: int = 30

    # GitHub
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""

    # SMTP / Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    ESCALATION_EMAIL: str = ""

    # Agent behaviour
    SCAN_INTERVAL_SECONDS: int = 30
    POST_FIX_VERIFY_DELAY_SECONDS: int = 120
    ENABLE_AUTO_FIX: bool = True
    DRY_RUN: bool = False
    DRIFT_AUTO_CORRECT: bool = False

    # API
    API_PORT: int = 8000
    API_KEY: str = "change-me-in-production"

    @property
    def target_namespaces_list(self) -> list[str]:
        """Return TARGET_NAMESPACES as a Python list."""
        return [ns.strip() for ns in self.TARGET_NAMESPACES.split(",") if ns.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton instance
settings = Settings()  # type: ignore[call-arg]

# Mutable runtime config (can be changed via Slack commands without restarting).
runtime_config: dict[str, Any] = {
    "DRY_RUN": settings.DRY_RUN,
    "ENABLE_AUTO_FIX": settings.ENABLE_AUTO_FIX,
    "DRIFT_AUTO_CORRECT": settings.DRIFT_AUTO_CORRECT,
    "AI_CONFIDENCE_THRESHOLD": settings.AI_CONFIDENCE_THRESHOLD,
}
