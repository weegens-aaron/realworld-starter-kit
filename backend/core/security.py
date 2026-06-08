"""Security primitives: password hashing and JWT issue/verify.

This module is the single source of truth for the two cryptographic concerns
the app has at the foundation layer:

* **Passwords** — hashed with bcrypt (the ``bcrypt`` library directly, no
  passlib wrapper) so the raw password never touches the database.
  ``hash_password`` / ``verify_password`` are the only blessed entry points.
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

import bcrypt
import jwt

from backend.core.config import get_settings

# bcrypt only consumes the first 72 bytes of input; bcrypt>=4.1 *raises* on
# longer input instead of silently truncating, so we truncate explicitly.
_BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or fails signature.

    A single exception type keeps the dependency layer simple: it catches one
    thing and decides (per dependency) whether that means 401 or anonymous.
    """


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def _prepare(password: str) -> bytes:
    """Encode and truncate ``password`` to bcrypt's 72-byte input window.

    Truncation matches bcrypt's own internal behaviour, so this only changes
    *when* the cut happens (here, explicitly) not *what* gets hashed. Callers
    should still enforce a sane max length at the API boundary.
    """
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of ``password`` as an ASCII string."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    """Check ``password`` against a stored ``hashed`` value.

    Returns ``False`` (never raises) on a mismatch *or* a malformed hash, so
    callers can treat "wrong password" and "garbage in the column" identically.
    """
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("ascii"))
    except (ValueError, TypeError):
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
