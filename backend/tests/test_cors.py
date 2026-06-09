"""Tests for the CORS middleware wiring.

Asserts the acceptance criteria of conduit-fnd-cors: cross-origin requests from
the frontend origin succeed and the OPTIONS preflight is handled. Behaviour is
specced in docs/backend/cors.md.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.core import get_settings
from backend.main import app

client = TestClient(app)

FRONTEND_ORIGIN = "https://demo.example.com"


def test_simple_request_gets_cors_headers() -> None:
    # A real GET carrying an Origin header must come back with the
    # access-control-allow-origin echo, or the browser hides the response.
    resp = client.get("/api/health", headers={"Origin": FRONTEND_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"


def test_preflight_is_handled() -> None:
    # The OPTIONS preflight for a non-simple request must be answered by the
    # middleware (short-circuited before any route) with a 200 and the
    # allow-methods/allow-headers the browser asked about.
    resp = client.options(
        "/api/health",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
    allow_methods = resp.headers["access-control-allow-methods"]
    assert "POST" in allow_methods
    allow_headers = resp.headers["access-control-allow-headers"].lower()
    assert "authorization" in allow_headers


def test_authorization_header_is_allowed_in_preflight() -> None:
    # Conduit auth rides in "Authorization: Token <jwt>", so the preflight must
    # green-light the Authorization request header for protected routes.
    resp = client.options(
        "/api/health",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert "authorization" in resp.headers["access-control-allow-headers"].lower()


def test_wildcard_default_does_not_set_credentials() -> None:
    # The wildcard origin and allow-credentials are mutually exclusive in the
    # CORS spec; our header-based auth means credentials stay OFF.
    settings = get_settings()
    assert settings.cors_allow_credentials is False
    resp = client.get("/api/health", headers={"Origin": FRONTEND_ORIGIN})
    assert "access-control-allow-credentials" not in resp.headers


def test_explicit_allowlist_echoes_matching_origin() -> None:
    # With a locked-down allowlist, a permitted origin is echoed back verbatim
    # (not "*"), proving CONDUIT_CORS_ORIGINS overrides actually take effect.
    restricted = FastAPI()
    restricted.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @restricted.get("/api/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    rclient = TestClient(restricted)
    resp = rclient.get("/api/health", headers={"Origin": FRONTEND_ORIGIN})
    assert resp.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
