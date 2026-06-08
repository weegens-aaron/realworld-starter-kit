"""Application entrypoint / factory.

Assembles the single FastAPI app that serves *both* halves of Conduit:

* the JSON API, mounted under ``/api`` (``backend.api.api_router``);
* the server-rendered HTML routes (``frontend.routes.html_router``) plus the
  ``/static`` asset mount.

Boot with ``uvicorn backend.main:app``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api import api_router
from backend.core import get_settings, register_exception_handlers
from frontend.routes import html_router


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    A factory (rather than a module-level ``app`` built inline) keeps tests
    able to spin up isolated instances and gives the cors/db/jwt beads a single
    seam to hook startup wiring into.
    """
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # Central error handling: every error comes back as RealWorld's
    # GenericErrorModel ({"errors": {key: [msgs]}}) with the documented status
    # codes. Wired before the routers so it blankets the whole app.
    register_exception_handlers(app)

    # JSON API first — one router owns the whole /api surface.
    app.include_router(api_router, prefix="/api")

    # Static assets for the HTML UI. The /static path matches DEFAULT_AVATAR_URL
    # in frontend/avatars.py — keep them in sync.
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    # Server-rendered HTML routes last, so the API/static mounts take precedence.
    app.include_router(html_router)

    return app


app = create_app()
