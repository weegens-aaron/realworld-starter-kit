"""Alembic migration environment for Conduit.

This wires Alembic into the *same* configuration and metadata the running app
uses, so migrations and the ORM can never silently disagree:

* **URL** — we don't hard-code a connection string in ``alembic.ini``. The URL
  comes from :func:`backend.core.config.get_settings` (i.e. ``DATABASE_URL``),
  normalised onto an async driver by :func:`backend.core.db._as_async_url` —
  the exact same path the app's engine takes. Pass ``-x dburl=...`` on the CLI
  to override for a one-off (CI, a throwaway SQLite DB for autogenerate, etc.).
* **Metadata** — importing :mod:`backend.models` is what registers every table
  on ``Base.metadata``; ``target_metadata`` points at it so ``--autogenerate``
  sees the full schema.

The engine is async (asyncpg in prod, aiosqlite in tests), so online migrations
run inside ``asyncio`` and hand a sync :class:`Connection` to Alembic via
``run_sync`` — Alembic's machinery is synchronous.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing the models package has the *side effect* of registering every ORM
# table on Base.metadata — which is precisely what autogenerate diffs against.
# Keep this import even though it looks unused (noqa) — it's load-bearing.
import backend.models  # noqa: F401
from alembic import context
from backend.core.config import get_settings
from backend.core.db import Base, _as_async_url

# Alembic Config object — access to values in alembic.ini.
config = context.config

# Set up Python logging from the ini file, if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The one metadata registry shared with the app. Drives --autogenerate.
target_metadata = Base.metadata


def _resolve_url() -> str:
    """Pick the DB URL (``-x dburl=`` wins, else settings) and make it async.

    Centralising this keeps Alembic honest with the app: same default URL, same
    driver normalisation. The ``-x dburl=`` escape hatch lets us point a single
    invocation at, say, an empty SQLite file for autogenerate without touching
    the environment.
    """
    override = context.get_x_argument(as_dictionary=True).get("dburl")
    url = override or get_settings().database_url
    return _as_async_url(url)


# Inject the resolved URL so async_engine_from_config(...) below builds an
# engine against the right database (the ini ships no real URL on purpose).
config.set_main_option("sqlalchemy.url", _resolve_url())


def run_migrations_offline() -> None:
    """Emit SQL for the migration without a live DBAPI connection (``--sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against a live (sync) connection.

    ``compare_type`` / ``compare_server_default`` make autogenerate notice
    column type and default drift, not just added/removed tables and columns.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Build an async engine and drive the (sync) migrations over it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (against a live async engine)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
