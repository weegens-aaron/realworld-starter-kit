"""Server-rendered HTML routes.

These routes render the page *shell* and public content directly from the
service layer (ADR 0001) — no self-HTTP hop back to ``/api``. Identity-dependent
content is hydrated client-side via the JSON API.

Only a scaffold home route exists today; the real route table (home, login,
register, editor, settings, profiles, articles) lands in ``conduit-fe-routing``
and the per-page beads.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from frontend.templates_env import get_templates

html_router = APIRouter(include_in_schema=False)


@html_router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Render the scaffold landing page.

    A placeholder shell that proves templating + static mounting work end to
    end. ``conduit-fe-layout`` replaces this with the real navbar/footer.
    """
    templates = get_templates()
    return templates.TemplateResponse(request, "index.html", {"app_name": "Conduit"})


__all__ = ["html_router"]
