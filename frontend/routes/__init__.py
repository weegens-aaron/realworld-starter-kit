"""Server-rendered HTML routes.

These routes render the page *shell* and public content directly from the
service layer (ADR 0001) — no self-HTTP hop back to ``/api``. Identity-dependent
content is hydrated client-side via the JSON API.

The full SELECTORS route table (home/feeds, auth, editor, settings, profiles,
articles) lives in :mod:`frontend.routes.pages`. This package re-exports its
``html_router`` so :mod:`backend.main` has one stable import seam.
"""

from frontend.routes.pages import html_router

__all__ = ["html_router"]
