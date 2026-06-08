"""Tests for the domain models: registration, constraints, relationships.

Everything runs against in-memory async SQLite so there's no Postgres in the
loop. SQLite needs ``PRAGMA foreign_keys=ON`` to actually *enforce* FKs, which
we don't rely on here — we assert on the ORM-level relationships and the
DB-level UNIQUE constraints, both of which SQLite honours out of the box.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models import (
    Article,
    Base,
    Comment,
    Favorite,
    Follow,
    Tag,
    User,
)


@pytest.fixture
async def session():
    """A live AsyncSession over a fresh in-memory SQLite schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _user(username: str) -> User:
    return User(
        username=username,
        email=f"{username}@example.com",
        password_hash="x",
    )


def test_all_models_registered_on_one_metadata() -> None:
    tables = set(Base.metadata.tables)
    assert {
        "users",
        "follows",
        "articles",
        "tags",
        "article_tags",
        "comments",
        "favorites",
    } <= tables


async def test_bio_and_image_are_nullable(session: AsyncSession) -> None:
    u = _user("alice")
    session.add(u)
    await session.commit()
    assert u.bio is None
    assert u.image is None


async def test_username_is_unique(session: AsyncSession) -> None:
    session.add(_user("bob"))
    await session.commit()
    dupe = User(username="bob", email="other@example.com", password_hash="x")
    session.add(dupe)
    with pytest.raises(sa.exc.IntegrityError):
        await session.commit()


async def test_email_is_unique(session: AsyncSession) -> None:
    session.add(_user("carol"))
    await session.commit()
    dupe = User(username="carol2", email="carol@example.com", password_hash="x")
    session.add(dupe)
    with pytest.raises(sa.exc.IntegrityError):
        await session.commit()


async def test_article_slug_is_unique(session: AsyncSession) -> None:
    author = _user("dave")
    session.add(author)
    await session.flush()
    session.add(
        Article(
            slug="hello",
            title="Hello",
            description="d",
            body="b",
            author_id=author.id,
        )
    )
    await session.commit()
    session.add(
        Article(
            slug="hello",
            title="Hello again",
            description="d",
            body="b",
            author_id=author.id,
        )
    )
    with pytest.raises(sa.exc.IntegrityError):
        await session.commit()


async def test_following_graph(session: AsyncSession) -> None:
    a, b = _user("ann"), _user("ben")
    session.add_all([a, b])
    await session.flush()
    session.add(Follow(follower_id=a.id, followed_id=b.id))
    await session.commit()

    # Reload with the follow collections eagerly populated.
    loaded = await session.scalar(
        sa.select(User).where(User.id == a.id).options(sa.orm.selectinload(User.following))
    )
    assert [u.username for u in loaded.following] == ["ben"]

    loaded_b = await session.scalar(
        sa.select(User).where(User.id == b.id).options(sa.orm.selectinload(User.followers))
    )
    assert [u.username for u in loaded_b.followers] == ["ann"]


async def test_tag_list_m2m(session: AsyncSession) -> None:
    author = _user("edith")
    session.add(author)
    await session.flush()
    art = Article(
        slug="tagged",
        title="T",
        description="d",
        body="b",
        author_id=author.id,
    )
    art.tags = [Tag(name="python"), Tag(name="fastapi")]
    session.add(art)
    await session.commit()
    # Drop the in-memory (insertion-order) collection so the load below actually
    # re-queries and exercises the relationship's `order_by`.
    session.expire_all()

    loaded = await session.scalar(
        sa.select(Article)
        .where(Article.slug == "tagged")
        .options(sa.orm.selectinload(Article.tags))
    )
    # `order_by="Tag.name"` keeps tagList deterministic.
    assert [t.name for t in loaded.tags] == ["fastapi", "python"]


async def test_favorites_count_column_property(session: AsyncSession) -> None:
    author = _user("frank")
    fan1, fan2 = _user("g1"), _user("g2")
    session.add_all([author, fan1, fan2])
    await session.flush()
    art = Article(
        slug="popular",
        title="P",
        description="d",
        body="b",
        author_id=author.id,
    )
    session.add(art)
    await session.flush()
    session.add_all(
        [
            Favorite(user_id=fan1.id, article_id=art.id),
            Favorite(user_id=fan2.id, article_id=art.id),
        ]
    )
    await session.commit()

    # favorites_count is deferred, so select it explicitly.
    count = await session.scalar(sa.select(Article.favorites_count).where(Article.id == art.id))
    assert count == 2

    # And a user can't favorite the same article twice.
    session.add(Favorite(user_id=fan1.id, article_id=art.id))
    with pytest.raises(sa.exc.IntegrityError):
        await session.commit()


async def test_comment_relationships(session: AsyncSession) -> None:
    author = _user("helen")
    session.add(author)
    await session.flush()
    art = Article(
        slug="commented",
        title="C",
        description="d",
        body="b",
        author_id=author.id,
    )
    session.add(art)
    await session.flush()
    session.add(Comment(body="nice!", author_id=author.id, article_id=art.id))
    await session.commit()

    loaded = await session.scalar(
        sa.select(Article)
        .where(Article.id == art.id)
        .options(sa.orm.selectinload(Article.comments))
    )
    assert len(loaded.comments) == 1
    assert loaded.comments[0].body == "nice!"
    assert loaded.comments[0].created_at is not None
