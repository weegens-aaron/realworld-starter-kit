"""Tests for the database wiring: URL normalisation, Base, and the session dep.

We prove the session *dependency* yields a working session by pointing the
factory at an in-memory async SQLite engine — no Postgres required in CI. The
asyncpg URL normalisation is exercised purely as string-in/string-out, so it
needs no driver either.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

import backend.core.db as db
from backend.core import Base, DbSession, get_db
from backend.models import Base as ModelsBase


def test_base_is_declarative() -> None:
    # Base carries a single shared metadata/registry for every model.
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")
    # The models package re-exports the *same* Base, not a copy.
    assert ModelsBase is Base


def test_dbsession_dependency_points_at_get_db() -> None:
    # DbSession is the pre-bound Annotated marker wrapping get_db.
    assert DbSession.__metadata__[0].dependency is get_db


def test_normalise_postgres_variants_to_asyncpg() -> None:
    for raw in (
        "postgres://u:p@host:5432/conduit",
        "postgresql://u:p@host:5432/conduit",
        "postgresql+psycopg://u:p@host:5432/conduit",
        "postgresql+psycopg2://u:p@host:5432/conduit",
    ):
        assert db._as_async_url(raw).startswith("postgresql+asyncpg://")


def test_normalise_leaves_async_and_sqlite_urls_alone() -> None:
    asyncpg = "postgresql+asyncpg://u:p@host/conduit"
    assert db._as_async_url(asyncpg) == asyncpg
    sqlite = "sqlite+aiosqlite:///:memory:"
    assert db._as_async_url(sqlite) == sqlite


async def test_get_db_yields_a_working_session(monkeypatch) -> None:
    """The session dependency yields a live AsyncSession that can query."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class _Thing(Base):
        __tablename__ = "things_under_test"
        id: Mapped[int] = mapped_column(primary_key=True)

    async with engine.begin() as conn:
        await conn.run_sync(_Thing.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(db, "async_session_factory", factory)

    agen = get_db()
    session = await agen.__anext__()
    try:
        assert isinstance(session, AsyncSession)
        session.add(_Thing(id=1))
        await session.commit()
        count = await session.scalar(sa.select(sa.func.count()).select_from(_Thing))
        assert count == 1
    finally:
        await agen.aclose()

    # Clean the throwaway table off the shared Base so it doesn't leak.
    Base.metadata.remove(_Thing.__table__)
    await engine.dispose()
