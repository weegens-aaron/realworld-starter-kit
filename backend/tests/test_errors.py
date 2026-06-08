"""Tests for the central GenericErrorModel exception handling.

Asserts the universal envelope (``{"errors": {key: [msgs]}}``) and the
status-code → key conventions the ``errors_*.hurl`` suite expects: 401 token,
403/404 resource, 409 field, 422 field keys.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.core import (
    APIError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
    register_exception_handlers,
)
from backend.core.deps import RequiredUser


# NOTE: must live at *module* scope, not inside ``_client()``. This file uses
# ``from __future__ import annotations``, so route annotations are strings that
# FastAPI resolves via ``get_type_hints`` against module globals. A model nested
# in a function is invisible to that lookup, so FastAPI fails to recognize it as
# the request body and collapses every validation error onto a single ``body``
# key — which would silently mask the per-field mapping we're trying to assert.
class _ValidateBody(BaseModel):
    email: str
    age: int


def _client() -> TestClient:
    """A throwaway app with the real handlers and one route per error kind."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/unauthorized")
    def _unauthorized() -> None:
        raise UnauthorizedError()

    @app.get("/forbidden")
    def _forbidden() -> None:
        raise ForbiddenError(resource="article")

    @app.get("/not-found")
    def _not_found() -> None:
        raise NotFoundError(resource="article")

    @app.get("/conflict")
    def _conflict() -> None:
        raise ConflictError("has already been taken", field="username")

    @app.get("/unprocessable")
    def _unprocessable() -> None:
        raise UnprocessableEntityError("is too short", field="password")

    @app.get("/http-401")
    def _http_401() -> None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="nope",
            headers={"WWW-Authenticate": "Token"},
        )

    @app.get("/teapot")
    def _teapot() -> None:
        raise HTTPException(status_code=418, detail="i am a teapot")

    @app.post("/validate")
    def _validate(body: _ValidateBody) -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/guarded")
    def _guarded(user: RequiredUser) -> dict[str, str]:
        return {"id": user.id}

    @app.get("/boom")
    def _boom() -> None:
        raise APIError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


def _errors(resp) -> dict[str, list[str]]:
    body = resp.json()
    assert set(body) == {"errors"}, body
    return body["errors"]


# --------------------------------------------------------------------------- #
# Status codes + key conventions
# --------------------------------------------------------------------------- #
def test_401_keyed_on_token_with_challenge() -> None:
    resp = _client().get("/unauthorized")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Token"
    assert list(_errors(resp)) == ["token"]


def test_403_keyed_on_resource() -> None:
    resp = _client().get("/forbidden")
    assert resp.status_code == 403
    assert "article" in _errors(resp)


def test_404_keyed_on_resource_with_default_message() -> None:
    resp = _client().get("/not-found")
    assert resp.status_code == 404
    assert _errors(resp) == {"article": ["article not found"]}


def test_409_keyed_on_field() -> None:
    resp = _client().get("/conflict")
    assert resp.status_code == 409
    assert _errors(resp) == {"username": ["has already been taken"]}


def test_422_explicit_field_error() -> None:
    resp = _client().get("/unprocessable")
    assert resp.status_code == 422
    assert _errors(resp) == {"password": ["is too short"]}


# --------------------------------------------------------------------------- #
# Framework-raised errors get reshaped too
# --------------------------------------------------------------------------- #
def test_bare_http_401_reshaped_and_keeps_header() -> None:
    resp = _client().get("/http-401")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Token"
    assert _errors(resp) == {"token": ["nope"]}


def test_bare_http_error_falls_back_to_body_key() -> None:
    resp = _client().get("/teapot")
    assert resp.status_code == 418
    assert _errors(resp) == {"body": ["i am a teapot"]}


def test_request_validation_maps_to_field_keys() -> None:
    resp = _client().post("/validate", json={"age": "not-an-int"})
    assert resp.status_code == 422
    errors = _errors(resp)
    # Missing field and bad-type field each get their own field key.
    assert "email" in errors
    assert "age" in errors
    assert all(isinstance(msgs, list) and msgs for msgs in errors.values())


def test_guarded_route_missing_token_is_envelope_401() -> None:
    resp = _client().get("/guarded")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Token"
    assert list(_errors(resp)) == ["token"]


def test_base_api_error_defaults_to_500_body_key() -> None:
    resp = _client().get("/boom")
    assert resp.status_code == 500
    assert _errors(resp) == {"body": ["kaboom"]}


# --------------------------------------------------------------------------- #
# Multi-message / custom errors mapping
# --------------------------------------------------------------------------- #
def test_errors_mapping_supports_multiple_messages() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/multi")
    def _multi() -> None:
        raise UnprocessableEntityError(errors={"email": ["can't be blank", "is invalid"]})

    resp = TestClient(app).get("/multi")
    assert resp.status_code == 422
    assert resp.json() == {"errors": {"email": ["can't be blank", "is invalid"]}}


def test_default_args_use_documented_keys() -> None:
    assert ForbiddenError().errors == {
        "resource": ["You do not have permission to perform this action."]
    }
    assert NotFoundError().errors == {"resource": ["resource not found"]}
    assert ConflictError().errors["conflict"]
    assert UnauthorizedError().headers == {"WWW-Authenticate": "Token"}
