"""Articles, their tags (M2M), and the favorite graph.

This module owns the content side of Conduit:

* :class:`Article` — the post. ``slug`` is unique (it's the public URL key);
  ``title`` / ``description`` / ``body`` are required text; ``author_id`` ties
  it to its :class:`~backend.models.user.User`. Timestamps come from
  :class:`~backend.models.mixins.TimestampMixin`.
* :class:`Tag` — a normalised tag name (unique). Joined to articles through the
  :data:`article_tags` association table, so an article's ``tagList`` is just
  the names of its ``tags`` relationship.
* :class:`Favorite` — a ``user favorited article`` edge (composite PK), the
  thing RealWorld's ``favoritesCount`` and per-user ``favorited`` flag are
  computed from. A read-only ``favorites_count`` column property is attached to
  :class:`Article` so the count can be selected/ordered in SQL without a
  Python-side ``len()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from backend.core.db import Base
from backend.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from backend.models.comment import Comment
    from backend.models.user import User


# Plain association table for the Article <-> Tag many-to-many. No extra
# columns ride on the edge, so a bare Table (not an association object) is the
# right, lightest-weight tool — YAGNI.
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column(
        "article_id",
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Article(Base, TimestampMixin):
    """A published post, addressed publicly by its unique ``slug``."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The URL-safe public key. Unique + indexed because every article fetch is
    # "find the one with this slug".
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    author: Mapped[User] = relationship(back_populates="articles")

    # M2M tags — `tagList` in the API is `[t.name for t in article.tags]`.
    tags: Mapped[list[Tag]] = relationship(
        secondary=article_tags,
        back_populates="articles",
        order_by="Tag.name",
    )

    comments: Mapped[list[Comment]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    favorited_by: Mapped[list[Favorite]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Article(id={self.id!r}, slug={self.slug!r})"


class Tag(Base):
    """A normalised tag. Shared across articles via :data:`article_tags`."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    articles: Mapped[list[Article]] = relationship(
        secondary=article_tags,
        back_populates="tags",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Tag(id={self.id!r}, name={self.name!r})"


class Favorite(Base):
    """A ``user favorited article`` edge — the unit of ``favoritesCount``.

    Composite-PK association object so a user can favorite a given article at
    most once. ``ondelete=CASCADE`` on both sides keeps the join table honest
    when either endpoint is deleted.
    """

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_favorite_pair"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped[User] = relationship(back_populates="favorites")
    article: Mapped[Article] = relationship(back_populates="favorited_by")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Favorite(user_id={self.user_id!r}, article_id={self.article_id!r})"


# `favoritesCount` as SQL, not Python: a correlated subquery the DB evaluates,
# so the count can be SELECTed and ORDER BY'd without loading every Favorite
# row. Declared after Favorite exists because it references its table.
Article.favorites_count = column_property(
    select(func.count(Favorite.user_id))
    .where(Favorite.article_id == Article.id)
    .correlate_except(Favorite)
    .scalar_subquery(),
    deferred=True,
)
