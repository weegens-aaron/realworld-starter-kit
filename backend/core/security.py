"""Security primitives: password hashing and JWT issue/verify.

This module is the single source of truth for the two cryptographic concerns
the app has at the foundation layer:

* **Passwords** — hashed with bcrypt via passlib's ``CryptContext`` so the
  raw password never touches the database. ``hash_password`` / ``verify_password``
  are the only blessed entry points.
* **JWTs** — symmetric (HS256) access tokens issued by ``create_access_token``
  and validated by ``decode_access_token`` (PyJWT under the hood). The token's
  subject (``sub``) carries the user id; ``username`` is included as a
  convenience claim so the optional/anonymous code paths can render a name
  without a DB round-trip.

Keeping *all* the crypto here means the FastAPI dependencies (see
``backend.core.deps``) and the users feature bead share one implementation —
no copy-pasted secret handling, no drifting algorithms. (DRY, and the Zen's
"There should be one obvious way to do it".)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from backend.core.config import get_settings

# One context, bcrypt scheme. ``deprecated="auto"`` lets us rotate schemes
# later (passlib will flag old hashes for re-hash) without breaking verify.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or fails signature.

    A single exception type keeps the dependency layer simple: it catches one
    thing and decides (per dependency) whether that means 401 or anonymous.
    """


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of ``password``.

    bcrypt silently truncates input beyond 72 bytes; callers should enforce a
    sane max length at the API boundary rather than relying on that quirk.
    """
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Check ``password`` against a stored ``hashed`` value.

    Returns ``False`` (never raises) on a mismatch *or* a malformed hash, so
    callers can treat "wrong password" and "garbage in the column" identically.
    """
    try:
        return _pwd_context.verify(password, hashed)
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# JSON Web Tokens
# --------------------------------------------------------------------------- #
def create_access_token(
    subject: str | int,
    *,
    username: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a signed access token whose ``sub`` claim is ``subject``.

    ``subject`` is stringified (JWT ``sub`` must be a string per spec). The
    optional ``username`` rides along as a non-standard claim so the optional
    auth path can name the user without hitting the DB. Expiry defaults to the
    configured ``jwt_expires_minutes``.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expires_minutes))

    payload: dict[str, object] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    if username is not None:
        payload["username"] = username

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    """Verify ``token`` and return its claims, or raise :class:`TokenError`.

    Wraps every PyJWT failure mode (bad signature, expired, malformed, missing
    ``sub``) into one ``TokenError`` so the dependency layer has a single,
    predictable thing to catch.
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:  # expired, bad signature, malformed, ...
        raise TokenError(str(exc)) from exc

    if not claims.get("sub"):
        raise TokenError("token is missing the 'sub' claim")
    return claims
