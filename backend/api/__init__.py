"""JSON API routers, aggregated under one ``api_router``.

Feature beads add their routers here (users, articles, profiles, ...). The
app factory mounts this single router at ``/api`` so there is exactly one
place that owns the API surface.
"""

from fastapi import APIRouter

from backend.api import health

api_router = APIRouter()
api_router.include_router(health.router)

__all__ = ["api_router"]
