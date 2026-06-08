"""Liveness probe.

A trivial, dependency-free endpoint so deploy tooling (and the scaffold's
acceptance check) can confirm the app booted and the router tree is wired
up. Mounted at ``/api/health`` via the app factory.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Response model for the health probe."""

    status: str = "ok"


@router.get("/health", response_model=HealthStatus, summary="Liveness probe")
def health() -> HealthStatus:
    """Return ``200 OK`` with a tiny JSON body when the app is alive."""
    return HealthStatus()
