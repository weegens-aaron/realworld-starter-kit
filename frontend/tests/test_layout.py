"""Layout/shell tests (conduit-fe-layout).

Asserts the base layout renders the RealWorld shell every page extends: the
navbar (.navbar / .navbar-brand / .nav-link), the .container, the footer, the
shared theme stylesheet, and BOTH auth states of the conditional nav (anon vs
signed-in) — since auth is client-owned (ADR 0001) the server renders both and
navbar.js flips them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import get_settings  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)


def _html(path: str) -> str:
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    return resp.text


# --- The shell renders on every page ----------------------------------------


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/profile/jane", "/article/x"])
def test_shell_chrome_on_every_page(path: str) -> None:
    html = _html(path)
    assert 'class="navbar navbar-light"' in html
    assert 'class="navbar-brand"' in html
    assert 'class="nav-link' in html  # leading quote; class may have " active"
    assert 'class="container"' in html
    assert "<footer>" in html


def test_brand_links_home_and_uses_app_name() -> None:
    html = _html("/")
    app_name = get_settings().app_name
    assert f'<a class="navbar-brand" href="/">{app_name.lower()}</a>' in html


def test_theme_stylesheet_is_linked() -> None:
    assert '<link rel="stylesheet" href="/static/css/styles.css" />' in _html("/")


def test_theme_stylesheet_is_served() -> None:
    resp = client.get("/static/css/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert ".navbar-brand" in resp.text


def test_navbar_js_bundle_is_wired() -> None:
    html = _html("/")
    assert '<script src="/static/js/auth.js"></script>' in html
    assert '<script src="/static/js/navbar.js"></script>' in html


# --- Conditional nav: both auth states render (JS flips them) ---------------


def test_anonymous_nav_links_present() -> None:
    html = _html("/")
    assert 'data-auth="anon"' in html
    assert 'href="/login">Sign in</a>' in html
    assert 'href="/register">Sign up</a>' in html
    # Home is always present.
    assert 'href="/">Home</a>' in html


def test_authenticated_nav_links_present_but_hidden() -> None:
    html = _html("/")
    # Authed items ship hidden; navbar.js reveals them once a token exists.
    assert 'data-auth="user" hidden' in html
    assert 'href="/editor">' in html
    assert "New Article" in html
    assert 'href="/settings">' in html
    assert "Settings" in html


def test_profile_nav_has_user_pic_with_default_avatar() -> None:
    html = _html("/")
    assert 'data-nav="profile"' in html
    assert 'class="user-pic"' in html
    # The avatar macro falls back to the shared default for null images.
    assert "default-avatar.svg" in html


def test_active_nav_link_reflects_current_page() -> None:
    assert 'class="nav-link active" href="/login"' in _html("/login")
    assert 'class="nav-link active" href="/register"' in _html("/register")
    assert 'class="nav-link active" href="/">Home</a>' in _html("/")


def test_footer_has_attribution_and_brand() -> None:
    html = _html("/")
    assert 'class="logo-font"' in html
    assert 'class="attribution"' in html
