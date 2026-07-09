"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --port 80

Routers
-------
auth     — GET  /              Google OAuth2 redirect callback
webhook  — POST /webhook       employee/contractor Jira events
webhook  — POST /maintenance_hiring  maintenance staff Jira events
health   — GET  /health        liveness probe
"""

import fast_api_logging as fl
from fastapi import FastAPI

from app.routers import auth, health, webhook

app = FastAPI(
    title="Accounts Creation RPA",
    description="Automated account provisioning via Jira webhooks and Google Workspace.",
    version="1.0.0",
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(webhook.router)
app.include_router(health.router)

# ── Startup log ───────────────────────────────────────────────────────────────
fl.info("FastAPI server has successfully started.")
