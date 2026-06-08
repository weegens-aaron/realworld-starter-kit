"""User & Profile schemas plus their request/response envelopes.

Two closely-related serialized shapes live here because they share the same
nullable ``bio``/``image`` pair (factored into :class:`_ProfileFields`):

* **User** — the *authenticated self*. Carries ``email`` and the JWT
  ``token`` alongside ``username``/``bio``/``image``. Only ever returned to the
  owner of the account.
* **Profile** — a *public view* of someone. Drops ``email``/``token`` and adds
  the viewer-relative ``following`` boolean.

Both normalise empty-string ``bio``/``image`` to ``null`` (see
:func:`backend.schemas.base.blank_to_none`) so the payload matches the spec
even when the DB or a client hands us ``""``.

The ``*Request`` models mirror the inbound bodies from ``openapi.yml``
(``{user: {...}}`` for register/login/update); the ``*Response`` models are the
``{user}`` / ``{profile}`` wrappers the API returns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import field_validator

from backend.schemas.base import Schema, blank_to_none

if TYPE_CHECKING:
    from backend.models import User


class _ProfileFields(Schema):
    """Shared nullable ``bio``/``image`` with empty-string -> ``null`` rules."""

    bio: str | None = None
    image: str | None = None

    @field_validator("bio", "image", mode="before")
    @classmethod
    def _normalize_blank(cls, value: object) -> object:
        return blank_to_none(value)


# --------------------------------------------------------------------------- #
# Serialized entities
# --------------------------------------------------------------------------- #
class UserSchema(_ProfileFields):
    """The authenticated user's own record — includes ``email`` and ``token``."""

    email: str
    token: str
    username: str

    @classmethod
    def from_user(cls, user: User, token: str) -> UserSchema:
        """Build from an ORM :class:`~backend.models.User` plus its JWT."""
        return cls(
            email=user.email,
            token=token,
            username=user.username,
            bio=user.bio,
            image=user.image,
        )


class ProfileSchema(_ProfileFields):
    """A public profile view — no ``email``/``token``, plus ``following``."""

    username: str
    following: bool = False

    @classmethod
    def from_user(cls, user: User, *, following: bool = False) -> ProfileSchema:
        """Build a profile of ``user`` as seen by a viewer (``following``)."""
        return cls(
            username=user.username,
            bio=user.bio,
            image=user.image,
            following=following,
        )


# --------------------------------------------------------------------------- #
# Response envelopes
# --------------------------------------------------------------------------- #
class UserResponse(Schema):
    """``{"user": {...}}`` — the wrapper for register/login/current/update."""

    user: UserSchema


class ProfileResponse(Schema):
    """``{"profile": {...}}`` — the wrapper for profile fetch/follow/unfollow."""

    profile: ProfileSchema


# --------------------------------------------------------------------------- #
# Request bodies (mirrors of openapi.yml)
# --------------------------------------------------------------------------- #
class NewUser(Schema):
    """Registration payload: ``{user: {username, email, password}}`` inner."""

    username: str
    email: str
    password: str


class NewUserRequest(Schema):
    user: NewUser


class LoginUser(Schema):
    """Login payload: ``{user: {email, password}}`` inner."""

    email: str
    password: str


class LoginUserRequest(Schema):
    user: LoginUser


class UpdateUser(_ProfileFields):
    """Update payload — every field optional; absent keys mean "leave as-is".

    ``bio``/``image`` still run through the blank->null normaliser, so clearing
    a field by sending ``""`` lands as ``null`` in storage.
    """

    email: str | None = None
    username: str | None = None
    password: str | None = None


class UpdateUserRequest(Schema):
    user: UpdateUser
