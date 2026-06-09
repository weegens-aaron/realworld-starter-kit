"""Jinja2 templating set-up for the server-rendered HTML.

Builds the ``Jinja2Templates`` instance the HTML routes render through, and
registers the shared avatar helpers (``avatar_src`` filter + ``DEFAULT_AVATAR_URL``
global) so null/empty avatars fall back consistently — one place, per ADR 0001
and the ``conduit-fe-avatar`` bead.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi.templating import Jinja2Templates

from backend.core import get_settings
from frontend.avatars import register_avatar_helpers


@lru_cache
def get_templates() -> Jinja2Templates:
    """Return the process-wide ``Jinja2Templates`` instance.

    Autoescaping is on by default (Jinja2Templates), which is the XSS
    mitigation ADR 0001 mandates given JWTs live in ``localStorage``.
    """
    settings = get_settings()
    templates = Jinja2Templates(directory=settings.templates_dir)
    register_avatar_helpers(templates.env)
    # ``app_name`` is a process-wide constant (settings), so it belongs as a
    # Jinja2 global next to DEFAULT_AVATAR_URL rather than being threaded
    # through every route's render context -- DRY, one obvious place.
    templates.env.globals["app_name"] = settings.app_name
    return templates
