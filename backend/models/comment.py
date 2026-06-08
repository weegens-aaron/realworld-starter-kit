"""Article comments.

A :class:`Comment` is a short body of text an author attaches to an article.
It carries timestamps (via :class:`~backend.models.mixins.TimestampMixin`) and
two foreign keys — ``author_id`` and ``article_id`` — both of which cascade on
delete so removing a user or an article doesn't strand orphan comments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.db import Base
from backend.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from backend.models.article import Article
    from backend.models.user import User


class Comment(Base, TimestampMixin):
    """A single comment on an article."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True, nullable=False
    )

    author: Mapped[User] = relationship(back_populates="comments")
    article: Mapped[Article] = relationship(back_populates="comments")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Comment(id={self.id!r}, article_id={self.article_id!r})"
