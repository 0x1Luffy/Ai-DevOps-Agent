"""FastAPI application — mounts all routers."""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health_gate import router as health_gate_router
from api.routes.approvals import router as approvals_router
from api.routes.jenkins_webhook import router as jenkins_router
from api.routes.metrics_endpoint import router as metrics_router
from api.routes.settings import router as settings_router
from api.routes.slack_webhook import router as slack_router

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AutoPilot DevOps Agent",
        version="1.0.0",
        description="Autonomous Kubernetes SRE and CI/CD incident responder",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(jenkins_router)
    app.include_router(approvals_router)
    app.include_router(slack_router)
    app.include_router(health_gate_router)
    app.include_router(metrics_router)
    app.include_router(settings_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe endpoint."""
        return {"status": "ok", "service": "autopilot-agent"}

    return app


app = create_app()
