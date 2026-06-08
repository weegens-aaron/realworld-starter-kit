"""Comment schemas: the entity, its envelopes, and the create payload.

A serialized comment is small — ``id``, timestamps, ``body``, and the author
rendered as a :class:`~backend.schemas.user.ProfileSchema` (so ``following`` is
viewer-relative, same as anywhere an author appears).

The list wrapper is ``{"comments": [...]}`` (no count — RealWorld doesn't
paginate comments), and the single wrapper is ``{"comment": {...}}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.schemas.base import Schema
from backend.schemas.user import ProfileSchema

if TYPE_CHECKING:
    from backend.models import Comment


class CommentSchema(Schema):
    """A single comment with its author embedded as a profile."""

    id: int
    created_at: datetime
    updated_at: datetime
    body: str
    author: ProfileSchema

    @classmethod
    def from_comment(cls, comment: Comment, *, author: ProfileSchema) -> CommentSchema:
        """Build from an ORM :class:`~backend.models.Comment` + author profile."""
        return cls(
            id=comment.id,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            body=comment.body,
            author=author,
        )


# --------------------------------------------------------------------------- #
# Response envelopes
# --------------------------------------------------------------------------- #
class CommentResponse(Schema):
    """``{"comment": {...}}`` — single-comment wrapper (e.g. after create)."""

    comment: CommentSchema


class MultipleCommentsResponse(Schema):
    """``{"comments": [...]}`` — comment-list wrapper (no count, unpaginated)."""

    comments: list[CommentSchema]


# --------------------------------------------------------------------------- #
# Request body (mirror of openapi.yml)
# --------------------------------------------------------------------------- #
class NewComment(Schema):
    """Create payload inner: ``{body}``."""

    body: str


class NewCommentRequest(Schema):
    comment: NewComment
