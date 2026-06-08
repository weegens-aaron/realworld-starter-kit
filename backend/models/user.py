"""User identity and the social ``follow`` graph.

Two tables live here because they're one concern: *who someone is* and *who
they follow*.

* :class:`User` — the account. ``username`` and ``email`` are unique (the API
  rejects duplicates of either); ``bio`` and ``image`` are nullable because a
  fresh signup has neither; ``password_hash`` holds the bcrypt digest from
  ``backend.core.security`` (the raw password never lands in a column).
* :class:`Follow` — a directed edge in the follow graph: ``follower_id``
  follows ``followed_id``. It's modelled as an explicit association *object*
  (not a bare table) so the edge can grow a ``created_at`` and so the
  relationships read naturally from either side.

The ``following`` / ``followers`` collections on :class:`User` ride the
``follows`` table via ``secondary``, which is what powers RealWorld's
``profile.following`` boolean: "does user A follow user B?" is just
``B in A.following`` (or a targeted EXISTS query in a service).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.db import Base

if TYPE_CHECKING:
    from backend.models.article import Article, Favorite
    from backend.models.comment import Comment


class User(Base):
    """A registered account and the root of everything they author/own."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Both are unique *and* indexed: the API looks users up by either, and the
    # uniqueness constraint is the contract the registration flow leans on.
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Profile extras — absent for a brand-new signup, hence nullable.
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # bcrypt digest (see backend.core.security). Never the plaintext.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Authored / owned content ---------------------------------------- #
    articles: Mapped[list[Article]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Follow graph ----------------------------------------------------- #
    # `following` = the users *this* user follows; `followers` = the users who
    # follow this one. Both project the self-referential `follows` edge through
    # its two foreign keys.
    following: Mapped[list[User]] = relationship(
        "User",
        secondary="follows",
        primaryjoin="User.id == Follow.follower_id",
        secondaryjoin="User.id == Follow.followed_id",
        back_populates="followers",
    )
    followers: Mapped[list[User]] = relationship(
        "User",
        secondary="follows",
        primaryjoin="User.id == Follow.followed_id",
        secondaryjoin="User.id == Follow.follower_id",
        back_populates="following",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"User(id={self.id!r}, username={self.username!r})"


class Follow(Base):
    """A directed ``follower -> followed`` edge in the social graph.

    Composite-PK association object: a given pair can exist at most once, and
    you can't follow without both endpoints. ``ondelete=CASCADE`` means
    deleting either user tidies up their edges automatically at the DB layer.
    """

    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="uq_follow_pair"),)

    follower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followed_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Follow(follower_id={self.follower_id!r}, followed_id={self.followed_id!r})"
