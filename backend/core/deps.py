"""FastAPI auth dependencies: required and optional current-user resolution.

RealWorld's API uses a non-standard ``Authorization`` scheme — the header is
``Authorization: Token <jwt>`` rather than the usual ``Bearer <jwt>``. This
module owns parsing that header and turning a valid JWT into a
:class:`CurrentUser`.

Two dependencies, two contracts:

* :func:`get_current_user` — **required**. No header, wrong scheme, or an
  invalid/expired token all yield ``401``. Use it to guard authenticated
  endpoints.
* :func:`get_optional_user` — **optional**. A missing or unusable token yields
  ``None`` (anonymous) instead of raising, so pages/endpoints that render
  differently for guests can branch on it.

The user is reconstructed straight from the token's claims. There is no DB
yet (the ``conduit-fnd-db`` bead lands the ORM), so resolving "the user" means
"the identity the token vouches for". When the User model exists, swap the
body of ``_user_from_claims`` for a real DB lookup keyed on ``sub`` — the
dependency signatures and the header handling stay put.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.core.security import TokenError, decode_access_token

# The custom scheme RealWorld mandates. Compared case-insensitively.
_AUTH_SCHEME = "Token"


class CurrentUser(BaseModel):
    """The authenticated identity carried by a verified JWT.

    ``token`` echoes the raw JWT so the users router can include it in the
    serialized RealWorld ``user`` payload (which embeds the token) without
    re-issuing one. ``id`` comes from the token ``sub`` claim.
    """

    id: str
    username: str | None = None
    token: str


def _extract_token(authorization: str | None) -> str | None:
    """Pull the JWT out of an ``Authorization: Token <jwt>`` header.

    Returns ``None`` when the header is absent or doesn't use the expected
    two-part ``Token <jwt>`` shape, letting callers decide what "no usable
    token" means for them.
    """
    if not authorization:
        return None
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != _AUTH_SCHEME.lower() or not credentials.strip():
        return None
    return credentials.strip()


def _user_from_claims(token: str, claims: dict[str, object]) -> CurrentUser:
    """Build a :class:`CurrentUser` from verified JWT claims.

    Seam for the DB bead: replace this with a lookup of ``claims['sub']`` and
    raise/return appropriately if the user was deleted. For now the token's own
    claims *are* the user of record.
    """
    return CurrentUser(
        id=str(claims["sub"]),
        username=claims.get("username"),  # type: ignore[arg-type]
        token=token,
    )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Resolve the authenticated user or raise ``401``.

    Required-auth dependency. Missing header, wrong scheme, and
    invalid/expired tokens all surface as ``401 Unauthorized`` with a
    ``WWW-Authenticate: Token`` challenge.
    """
    token = _extract_token(authorization)
    if token is None:
        raise _unauthorized("Authentication credentials were not provided.")
    try:
        claims = decode_access_token(token)
    except TokenError as exc:
        raise _unauthorized("Invalid or expired token.") from exc
    return _user_from_claims(token, claims)


def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser | None:
    """Resolve the user if a valid token is present, else ``None``.

    Optional-auth dependency: never raises for auth reasons. A missing header,
    a non-``Token`` scheme, or an invalid/expired token all mean "anonymous".
    """
    token = _extract_token(authorization)
    if token is None:
        return None
    try:
        claims = decode_access_token(token)
    except TokenError:
        return None
    return _user_from_claims(token, claims)


def _unauthorized(detail: str) -> HTTPException:
    """Build a ``401`` advertising the custom ``Token`` auth scheme."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": _AUTH_SCHEME},
    )


# Pre-bound dependency markers so routers read cleanly:
#     async def route(user: RequiredUser): ...
#     async def route(user: OptionalUser): ...
RequiredUser = Annotated[CurrentUser, Depends(get_current_user)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_optional_user)]
