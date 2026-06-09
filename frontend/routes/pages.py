"""Server-rendered HTML route table for every SELECTORS route.

This module wires *routing only* (conduit-fe-routing): every URL the e2e
SELECTORS contract / url-navigation expectations care about resolves to a page
shell. The per-page beads later replace each page's body with the real
RealWorld markup; here we prove the route resolves, that deep links work, and
that query params (``feed`` / ``page``) and path params (``tag`` / ``slug`` /
``username``) are parsed and surfaced.

Auth model (ADR 0001): there is no server session. Protected routes
(``/editor``, ``/editor/:slug``, ``/settings``) are *served* to everyone but
carry a pre-paint ``<head>`` guard (see ``page.html``) that bounces
unauthenticated viewers to ``/login`` before any content paints. The server
never redirects for auth because it cannot see the client-only JWT.

Every handler renders the shared ``page.html`` scaffold through one helper
(``_render``) so the shell, the protected-guard wiring and the route-root class
convention live in exactly one place — DRY, per the Zen of Python's "There
should be one obvious way to do it."
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from frontend.templates_env import get_templates

html_router = APIRouter(include_in_schema=False)

# RealWorld feeds: the home page shows either the global feed or, for a signed
# in user, "Your Feed" (?feed=following). Anything else is treated as global.
_FOLLOWING_FEED = "following"
_GLOBAL_FEED = "global"


def _render(
    request: Request,
    *,
    page: str,
    page_class: str,
    page_title: str,
    protected: bool = False,
    params: dict[str, object] | None = None,
) -> HTMLResponse:
    """Render the shared page scaffold with route-specific context.

    ``page_class`` is the RealWorld route-root class (``home-page``,
    ``auth-page``, ``editor-page``, ``settings-page``, ``profile-page``,
    ``article-page``) the url-navigation expectations match on. ``params`` is
    surfaced as ``data-*`` attributes so deep-link state (active tag, page
    number, feed, profile username, article slug) is observable.
    """
    templates = get_templates()
    return templates.TemplateResponse(
        request,
        "page.html",
        {
            "page": page,
            "page_class": page_class,
            "page_title": page_title,
            "protected": protected,
            "params": params or {},
        },
    )


def _page_number(request: Request) -> int:
    """Parse the ``?page=N`` pagination param, defaulting to 1.

    Non-numeric, missing or sub-1 values collapse to page 1 so a hand-typed or
    malformed deep link never 500s or pages into the void.
    """
    raw = request.query_params.get("page")
    try:
        number = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1
    return number if number >= 1 else 1


def _feed(request: Request) -> str:
    """Parse the ``?feed=`` home-page param, normalising to global/following."""
    return _FOLLOWING_FEED if request.query_params.get("feed") == _FOLLOWING_FEED else _GLOBAL_FEED


# --- Home / feeds -----------------------------------------------------------


@html_router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Home: global feed by default, ``?feed=following`` for Your Feed.

    ``?page=N`` deep-links into the paginated feed. Both are surfaced as
    ``data-*`` so the client hydrator (and the e2e suite) can read intended
    state; the personalized "following" content itself is hydrated client-side
    once the JWT is known.
    """
    return _render(
        request,
        page="home",
        page_class="home-page",
        page_title="Home",
        params={"feed": _feed(request), "page": _page_number(request)},
    )


@html_router.get("/tag/{tag}", response_class=HTMLResponse)
def tag_feed(request: Request, tag: str) -> HTMLResponse:
    """Tag feed: the home page filtered to ``#{tag}`` (``?page=N`` paginates)."""
    return _render(
        request,
        page="home",
        page_class="home-page",
        page_title=f"#{tag}",
        params={"feed": "tag", "tag": tag, "page": _page_number(request)},
    )


# --- Auth -------------------------------------------------------------------


@html_router.get("/login", response_class=HTMLResponse)
def login(request: Request) -> HTMLResponse:
    """Sign-in page (public)."""
    return _render(request, page="login", page_class="auth-page", page_title="Sign in")


@html_router.get("/register", response_class=HTMLResponse)
def register(request: Request) -> HTMLResponse:
    """Sign-up page (public)."""
    return _render(request, page="register", page_class="auth-page", page_title="Sign up")


# --- Editor (protected) -----------------------------------------------------


@html_router.get("/editor", response_class=HTMLResponse)
def editor_new(request: Request) -> HTMLResponse:
    """New-article editor (protected: guarded pre-paint to /login)."""
    return _render(
        request,
        page="editor",
        page_class="editor-page",
        page_title="New Article",
        protected=True,
    )


@html_router.get("/editor/{slug}", response_class=HTMLResponse)
def editor_edit(request: Request, slug: str) -> HTMLResponse:
    """Edit-article editor for ``slug`` (protected: guarded pre-paint)."""
    return _render(
        request,
        page="editor",
        page_class="editor-page",
        page_title="Edit Article",
        protected=True,
        params={"slug": slug},
    )


# --- Settings (protected) ---------------------------------------------------


@html_router.get("/settings", response_class=HTMLResponse)
def settings(request: Request) -> HTMLResponse:
    """User settings (protected: guarded pre-paint to /login)."""
    return _render(
        request,
        page="settings",
        page_class="settings-page",
        page_title="Settings",
        protected=True,
    )


# --- Profiles ---------------------------------------------------------------


@html_router.get("/profile/{username}", response_class=HTMLResponse)
def profile(request: Request, username: str) -> HTMLResponse:
    """Public profile: the user's authored articles tab."""
    return _render(
        request,
        page="profile",
        page_class="profile-page",
        page_title=f"@{username}",
        params={"username": username, "tab": "authored"},
    )


@html_router.get("/profile/{username}/favorites", response_class=HTMLResponse)
def profile_favorites(request: Request, username: str) -> HTMLResponse:
    """Public profile: the user's favorited articles tab."""
    return _render(
        request,
        page="profile",
        page_class="profile-page",
        page_title=f"@{username}",
        params={"username": username, "tab": "favorites"},
    )


# --- Article ----------------------------------------------------------------


@html_router.get("/article/{slug}", response_class=HTMLResponse)
def article(request: Request, slug: str) -> HTMLResponse:
    """Public article read view for ``slug``."""
    return _render(
        request,
        page="article",
        page_class="article-page",
        page_title="Article",
        params={"slug": slug},
    )


__all__ = ["html_router"]
