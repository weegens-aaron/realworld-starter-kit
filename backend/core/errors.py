"""Central error handling: the RealWorld ``GenericErrorModel`` everywhere.

Every error this API emits — whether we raised it deliberately, FastAPI raised
it for us (request validation), or Starlette raised a bare ``HTTPException`` —
comes back in *one* JSON shape::

    {"errors": {"<key>": ["<message>", ...]}}

That shape is RealWorld's ``GenericErrorModel``. Keeping a single envelope (and
a single place that builds it) means clients only ever parse one thing, and the
``errors_*.hurl`` acceptance suite can assert against stable keys.

Status-code → key conventions (what the hurl suite expects):

* **401** — auth credentials missing/invalid. Key ``token``. Carries a
  ``WWW-Authenticate: Token`` challenge (RealWorld's non-standard scheme).
* **403** — forbidden. Key is the *resource* you weren't allowed to touch
  (defaults to ``resource``).
* **404** — not found. Key is the *resource* that's missing (defaults to
  ``resource``).
* **409** — conflict, e.g. a username already taken. Key is the offending
  *field* (e.g. ``username``).
* **422** — validation. One key per invalid *field*; values are the per-field
  messages, mapped straight off Pydantic/FastAPI's request-validation errors.

Routers should raise the typed :class:`APIError` subclasses below rather than
hand-rolling responses. The app factory wires the handlers in via
:func:`register_exception_handlers`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

# RealWorld's auth scheme is ``Token``, not ``Bearer`` (see backend.core.deps).
# A 401 advertises it so well-behaved clients know how to authenticate.
_AUTH_SCHEME = "Token"

# Fallback ``errors`` key when a bare HTTPException gives us nothing better to
# go on. Mirrors the status → key conventions documented in the module header.
_STATUS_KEYS: dict[int, str] = {
    401: "token",
    403: "resource",
    404: "resource",
    409: "conflict",
}
_DEFAULT_KEY = "body"

# Type alias for the inner ``errors`` mapping: field/resource → list of messages.
Errors = Mapping[str, Iterable[str]]


class GenericErrorModel(BaseModel):
    """OpenAPI documentation for the universal error envelope.

    Exists so the generated schema advertises the real response shape; the
    handlers below build the same structure by hand (they need to set status
    codes and headers a ``response_model`` can't).
    """

    errors: dict[str, list[str]]


def _normalize(errors: Errors) -> dict[str, list[str]]:
    """Coerce an ``errors`` mapping into ``{str: [str, ...]}`` form."""
    return {str(key): [str(m) for m in messages] for key, messages in errors.items()}


# --------------------------------------------------------------------------- #
# Typed exceptions — raise these from routers/services.
# --------------------------------------------------------------------------- #
class APIError(Exception):
    """Base for any error that should serialize to ``GenericErrorModel``.

    Subclasses fix a ``status_code`` and sensible defaults; instances carry the
    concrete ``errors`` mapping and any extra response ``headers`` (e.g. the
    auth challenge on a 401).
    """

    status_code: int = 500
    default_key: str = _DEFAULT_KEY
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        key: str | None = None,
        errors: Errors | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if errors is not None:
            self.errors = _normalize(errors)
        else:
            self.errors = {
                key or self.default_key: [message or self.default_message],
            }
        self.headers = dict(headers) if headers else None
        super().__init__(self.errors)


class UnauthorizedError(APIError):
    """401 — authentication credentials are missing, malformed, or expired."""

    status_code = 401
    default_key = "token"
    default_message = "Authentication credentials were not provided or are invalid."

    def __init__(self, message: str | None = None, **kwargs: object) -> None:
        headers = dict(kwargs.pop("headers", None) or {})  # type: ignore[arg-type]
        headers.setdefault("WWW-Authenticate", _AUTH_SCHEME)
        super().__init__(message, headers=headers, **kwargs)  # type: ignore[arg-type]


class ForbiddenError(APIError):
    """403 — authenticated, but not allowed to touch this ``resource``."""

    status_code = 403
    default_key = "resource"
    default_message = "You do not have permission to perform this action."

    def __init__(
        self,
        message: str | None = None,
        *,
        resource: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, key=resource or self.default_key, **kwargs)  # type: ignore[arg-type]


class NotFoundError(APIError):
    """404 — the requested ``resource`` does not exist."""

    status_code = 404
    default_key = "resource"
    default_message = "The requested resource was not found."

    def __init__(
        self,
        message: str | None = None,
        *,
        resource: str | None = None,
        **kwargs: object,
    ) -> None:
        resolved = resource or self.default_key
        super().__init__(
            message or f"{resolved} not found",
            key=resolved,
            **kwargs,  # type: ignore[arg-type]
        )


class ConflictError(APIError):
    """409 — the request conflicts with existing state (e.g. username taken)."""

    status_code = 409
    default_key = "conflict"
    default_message = "The request conflicts with the current state."

    def __init__(
        self,
        message: str | None = None,
        *,
        field: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, key=field or self.default_key, **kwargs)  # type: ignore[arg-type]


class UnprocessableEntityError(APIError):
    """422 — semantically invalid input, keyed by ``field``.

    For *request-shape* validation FastAPI raises this for us; reach for this
    class when business rules reject otherwise well-formed input.
    """

    status_code = 422
    default_key = "body"
    default_message = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        field: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, key=field or self.default_key, **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Handlers — turn exceptions into the one true envelope.
# --------------------------------------------------------------------------- #
def _envelope(
    status_code: int,
    errors: dict[str, list[str]],
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the canonical ``{"errors": {...}}`` JSON response."""
    return JSONResponse(
        status_code=status_code,
        content={"errors": errors},
        headers=dict(headers) if headers else None,
    )


async def _api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    """Serialize a deliberately raised :class:`APIError`."""
    return _envelope(exc.status_code, exc.errors, exc.headers)


async def _http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Wrap a bare ``HTTPException`` (ours or FastAPI's) into the envelope.

    The auth dependencies in ``backend.core.deps`` raise plain 401
    ``HTTPException``s; this reshapes them — and any other framework-raised
    HTTP error — into ``GenericErrorModel`` while preserving headers such as
    the ``WWW-Authenticate`` challenge.
    """
    key = _STATUS_KEYS.get(exc.status_code, _DEFAULT_KEY)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _envelope(exc.status_code, {key: [detail]}, exc.headers)


def _field_key(loc: tuple[object, ...]) -> str:
    """Reduce a Pydantic error ``loc`` to a single field key.

    ``loc`` looks like ``("body", "user", "email")``; clients care about the
    field (``email``), not where in the request it sat, so we drop the leading
    request-part marker and use the most specific remaining segment.
    """
    parts = [p for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return str(parts[-1]) if parts else _DEFAULT_KEY


async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map FastAPI's request-validation errors to field-keyed 422s."""
    errors: dict[str, list[str]] = {}
    for err in exc.errors():
        key = _field_key(tuple(err.get("loc", ())))
        errors.setdefault(key, []).append(str(err.get("msg", "is invalid")))
    return _envelope(422, errors)


def register_exception_handlers(app: FastAPI) -> None:
    """Install every handler that yields the ``GenericErrorModel`` envelope.

    Called once from ``create_app()``. Registers, in order of specificity:
    our typed :class:`APIError`, request-validation errors, and a catch-all for
    bare ``HTTPException``s.
    """
    app.add_exception_handler(APIError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
