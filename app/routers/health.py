"""
Health-check router.

  GET /health — returns 200 + JSON status when the server is up.

Useful for load balancers, Docker HEALTHCHECK, and monitoring tools.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["ops"])
async def health_check():
    """Return a simple liveness response."""
    return {"status": "ok"}
