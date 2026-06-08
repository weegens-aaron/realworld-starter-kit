"""Async SQLAlchemy 2.0 engine, session factory, and the FastAPI session dep.

One place owns the database wiring so the rest of the app never touches an
engine or a sessionmaker directly — it just asks for a session via the
:data:`DbSession` dependency. Three exports matter downstream:

* :class:`Base` — the declarative base every ORM model inherits from. The
  ``conduit-fnd-models`` bead (and friends) ``from backend.core.db import Base``
  (or the re-export in ``backend.models``) and declare their tables against it.
* :data:`async_session_factory` — an :class:`async_sessionmaker` bound to the
  process-wide :data:`engine`. Tests monkeypatch this to point at a throwaway
  database without touching :func:`get_db`.
* :func:`get_db` / :data:`DbSession` — the FastAPI dependency that yields a
  live :class:`AsyncSession` per request and guarantees it's closed afterwards.

Engine creation is intentionally *lazy about connecting*: building the engine
opens no sockets, so importing this module (and booting the app) never requires
a running Postgres. The first real query is what dials out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings

# Drivers we transparently rewrite onto asyncpg. ``postgres`` is the legacy
# scheme some hosts still emit (and which SQLAlchemy itself rejects); the
# psycopg variants are the common *sync* drivers a human might paste in.
_SYNC_POSTGRES_DRIVERS = frozenset(
    {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
)


def _as_async_url(url: str) -> str:
    """Normalise a connection URL onto an async-capable driver.

    The async engine needs an async driver. Rather than make every caller
    remember to type ``postgresql+asyncpg://``, we accept the ergonomic /
    platform-injected forms (``postgres://``, ``postgresql://``, the psycopg
    sync drivers) and rewrite the Postgres ones to asyncpg. Anything already
    async — or a non-Postgres URL like ``sqlite+aiosqlite://`` used in tests —
    passes straight through untouched.
    """
    parsed = make_url(url)
    if parsed.drivername in _SYNC_POSTGRES_DRIVERS:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed.render_as_string(hide_password=False)


def create_engine(url: str | None = None) -> AsyncEngine:
    """Build a configured :class:`AsyncEngine` (without connecting).

    Factored out so tests — and Alembic, later — can spin up an engine against
    an arbitrary URL. ``pool_pre_ping`` quietly recycles connections a flaky
    network (or a Postgres restart) left for dead, which is cheap insurance for
    a long-lived web process.
    """
    settings = get_settings()
    target = url if url is not None else settings.database_url
    return create_async_engine(
        _as_async_url(target),
        pool_pre_ping=True,
        echo=settings.debug,
    )


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model.

    Carries the single :class:`~sqlalchemy.MetaData` registry that Alembic
    autogenerate and ``Base.metadata.create_all`` both key off of. Models live
    in their own beads; they import *this* so there's exactly one registry.
    """


# Process-wide engine + session factory. ``expire_on_commit=False`` keeps ORM
# objects usable after a commit (you can still read their attributes when
# serialising a response), which is the sane default for a web request flow.
engine: AsyncEngine = create_engine()
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped :class:`AsyncSession`, closing it on the way out.

    The ``async with`` block owns the lifecycle: the session is returned to the
    pool (and rolled back if the request raised mid-transaction) no matter how
    the endpoint exits. Commit explicitly in your service/route when you mean
    to persist — this dependency deliberately doesn't auto-commit.
    """
    async with async_session_factory() as session:
        yield session


# Pre-bound marker so routes read cleanly: ``async def route(db: DbSession): ...``
DbSession = Annotated[AsyncSession, Depends(get_db)]
