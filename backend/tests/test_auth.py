"""Tests for the JWT auth foundation: hashing, token issue/verify, deps."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core import (
    CurrentUser,
    OptionalUser,
    RequiredUser,
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def test_hash_password_roundtrips() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"  # not stored in the clear
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hashed = hash_password("s3cret")
    assert verify_password("not-it", hashed) is False


def test_verify_handles_garbage_hash_gracefully() -> None:
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_hash_is_salted_unique() -> None:
    assert hash_password("same") != hash_password("same")


# --------------------------------------------------------------------------- #
# JWT issue / verify
# --------------------------------------------------------------------------- #
def test_token_roundtrip_carries_subject_and_username() -> None:
    token = create_access_token(42, username="jane")
    claims = decode_access_token(token)
    assert claims["sub"] == "42"
    assert claims["username"] == "jane"


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(1)
    with pytest.raises(TokenError):
        decode_access_token(token + "tampered")


def test_decode_rejects_expired_token() -> None:
    token = create_access_token(1, expires_delta=timedelta(seconds=-1))
    with pytest.raises(TokenError):
        decode_access_token(token)


# --------------------------------------------------------------------------- #
# FastAPI dependencies — exercised through a throwaway app
# --------------------------------------------------------------------------- #
def _client() -> TestClient:
    app = FastAPI()

    @app.get("/required")
    def required(user: RequiredUser) -> dict[str, object]:
        return {"id": user.id, "username": user.username, "token": user.token}

    @app.get("/optional")
    def optional(user: OptionalUser) -> dict[str, object]:
        if user is None:
            return {"anonymous": True}
        return {"anonymous": False, "id": user.id}

    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Token {token}"}


def test_required_dep_resolves_valid_token() -> None:
    token = create_access_token(7, username="kate")
    resp = _client().get("/required", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"id": "7", "username": "kate", "token": token}


def test_required_dep_401_without_header() -> None:
    resp = _client().get("/required")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Token"


def test_required_dep_401_on_invalid_token() -> None:
    resp = _client().get("/required", headers=_auth("garbage"))
    assert resp.status_code == 401


def test_required_dep_401_on_wrong_scheme() -> None:
    token = create_access_token(1)
    resp = _client().get("/required", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_optional_dep_anonymous_without_header() -> None:
    resp = _client().get("/optional")
    assert resp.status_code == 200
    assert resp.json() == {"anonymous": True}


def test_optional_dep_anonymous_on_invalid_token() -> None:
    resp = _client().get("/optional", headers=_auth("garbage"))
    assert resp.status_code == 200
    assert resp.json() == {"anonymous": True}


def test_optional_dep_resolves_valid_token() -> None:
    token = create_access_token(99)
    resp = _client().get("/optional", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"anonymous": False, "id": "99"}


def test_current_user_model_shape() -> None:
    user = CurrentUser(id="1", token="abc")
    assert user.username is None
