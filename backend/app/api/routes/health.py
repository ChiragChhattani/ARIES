"""
Health check endpoint.

WHY A HEALTH ENDPOINT?
----------------------
1. Deployment platforms (Render, AWS, etc.) ping this endpoint to know
   if your app is alive. If it returns non-200, they restart the container.
2. Load balancers use it to decide whether to route traffic to this instance.
3. Developers use it as a quick smoke test: "Is the server running?"

A good health check tests real dependencies (database, external APIs)
rather than just returning {"status": "ok"} unconditionally.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Application health check.

    Returns:
        Basic health status, version, and environment information.
        Does NOT expose secrets or internal details.
    """
    settings = get_settings()

    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
