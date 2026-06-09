"""Routing tests for every SELECTORS HTML route (conduit-fe-routing).

Asserts that each route resolves to its page (correct route-root class),
that deep links + query params (feed / page / tag / slug / username) are
parsed and surfaced, and that protected routes ship the pre-paint /login
guard (ADR 0001, Decision (c)).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the repo root importable so `backend` / `frontend` resolve as packages.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.main import app  # noqa: E402

client = TestClient(app)


def _html(path: str) -> str:
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    assert "text/html" in resp.headers["content-type"]
    return resp.text


# --- Every SELECTORS route resolves to its route-root class -----------------


@pytest.mark.parametrize(
    ("path", "page_class"),
    [
        ("/", "home-page"),
        ("/?feed=following", "home-page"),
        ("/?page=2", "home-page"),
        ("/tag/dragons", "home-page"),
        ("/tag/dragons?page=3", "home-page"),
        ("/login", "auth-page"),
        ("/register", "auth-page"),
        ("/editor", "editor-page"),
        ("/editor/some-slug", "editor-page"),
        ("/settings", "settings-page"),
        ("/profile/jane", "profile-page"),
        ("/profile/jane/favorites", "profile-page"),
        ("/article/how-to-train-your-dragon", "article-page"),
    ],
)
def test_route_resolves_to_page(path: str, page_class: str) -> None:
    assert f'class="{page_class}"' in _html(path)


# --- Query / path params are parsed and surfaced ----------------------------


def test_home_defaults_to_global_feed_page_one() -> None:
    html = _html("/")
    assert 'data-feed="global"' in html
    assert 'data-page="1"' in html


def test_home_following_feed_deep_link() -> None:
    assert 'data-feed="following"' in _html("/?feed=following")


def test_home_pagination_deep_link() -> None:
    assert 'data-page="5"' in _html("/?page=5")


def test_home_bad_page_param_falls_back_to_one() -> None:
    assert 'data-page="1"' in _html("/?page=notanumber")
    assert 'data-page="1"' in _html("/?page=0")
    assert 'data-page="1"' in _html("/?page=-3")


def test_unknown_feed_normalises_to_global() -> None:
    assert 'data-feed="global"' in _html("/?feed=bogus")


def test_tag_route_surfaces_tag_and_page() -> None:
    html = _html("/tag/dragons?page=2")
    assert 'data-tag="dragons"' in html
    assert 'data-page="2"' in html


def test_editor_edit_surfaces_slug() -> None:
    assert 'data-slug="my-article"' in _html("/editor/my-article")


def test_article_surfaces_slug() -> None:
    assert 'data-slug="my-article"' in _html("/article/my-article")


def test_profile_surfaces_username_and_tab() -> None:
    html = _html("/profile/jane")
    assert 'data-username="jane"' in html
    assert 'data-tab="authored"' in html


def test_profile_favorites_tab() -> None:
    html = _html("/profile/jane/favorites")
    assert 'data-username="jane"' in html
    assert 'data-tab="favorites"' in html


# --- Protected routes ship the pre-paint guard, public ones do not ----------


@pytest.mark.parametrize("path", ["/editor", "/editor/x", "/settings"])
def test_protected_routes_have_login_guard(path: str) -> None:
    html = _html(path)
    assert "localStorage.getItem('jwtToken')" in html
    assert "window.location.replace('/login')" in html


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/profile/jane", "/article/x"])
def test_public_routes_have_no_guard(path: str) -> None:
    assert "window.location.replace('/login')" not in _html(path)


# --- Page title renders app_name (regression: phantom Jinja2 global) --------


def test_title_includes_app_name() -> None:
    """`page.html` references {{ app_name }}; guard it is actually supplied.

    Regression for the phantom-global bug where the title rendered as
    ``Home — `` (empty) because ``app_name`` was never in the template
    context. It now lives as a Jinja2 global in ``templates_env``.
    """
    from backend.core import get_settings

    app_name = get_settings().app_name
    assert f"<title>Home — {app_name}</title>" in _html("/")
