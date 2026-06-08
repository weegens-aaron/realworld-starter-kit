"""Smoke tests for the scaffold: the app boots and routes are wired."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_home_renders_html() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Conduit" in resp.text


def test_packages_import_cleanly() -> None:
    # Importing the source trees must not explode at collection time.
    import backend  # noqa: F401
    import backend.api  # noqa: F401
    import backend.core  # noqa: F401
    import backend.models  # noqa: F401
    import backend.services  # noqa: F401
    import frontend  # noqa: F401
    import frontend.routes  # noqa: F401
