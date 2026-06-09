# ![RealWorld Example App](logo.png)

> ### [YOUR_FRAMEWORK] codebase containing real world examples (CRUD, auth, advanced patterns, etc) that adheres to the [RealWorld](https://github.com/gothinkster/realworld) spec and API.


### [Demo](https://demo.realworld.build/)&nbsp;&nbsp;&nbsp;&nbsp;[RealWorld](https://github.com/gothinkster/realworld)


This codebase was created to demonstrate a fully fledged fullstack application built with **[YOUR_FRAMEWORK]** including CRUD operations, authentication, routing, pagination, and more.

We've gone to great lengths to adhere to the **[YOUR_FRAMEWORK]** community styleguides & best practices.

For more information on how to this works with other frontends/backends, head over to the [RealWorld](https://github.com/gothinkster/realworld) repo.


# How it works

Conduit is a **single FastAPI service** that serves both halves of the app:

- the **JSON API** under `/api` (`backend/` — `api`, `models`, `services`, `core`);
- the **server-rendered HTML UI** (Jinja2 + HTMX) plus `/static` assets
  (`frontend/` — `templates`, `static`, `routes`).

One process, one address space: the HTML routes call the service layer
directly (no self-HTTP hop). See
[`docs/adr/0001`](docs/adr/0001-htmx-jwt-localstorage-rendering-strategy.md)
for the auth/rendering strategy.

# Getting started

Requires [uv](https://docs.astral.sh/uv/), Python 3.11+, and
[Docker](https://docs.docker.com/get-docker/) (for the Postgres container).

```bash
uv sync --extra dev          # install deps into .venv (lockfile: uv.lock)
cp .env.example .env         # copy the env template (tweak if you like)
make dev                     # Postgres -> migrations -> uvicorn --reload
# -> http://127.0.0.1:8000  ·  health: GET /api/health
```

`make dev` is the one-command dev boot. Under the hood it runs
[`scripts/dev.sh`](scripts/dev.sh), which starts the Postgres container, waits
for it to report healthy, applies migrations (`alembic upgrade head`, skipped
gracefully until the migration bead lands), then launches uvicorn. No `make`?
Run `./scripts/dev.sh` directly — it does the same thing.

Don't have Docker, or already run your own Postgres? Point `DATABASE_URL` at it
and skip compose:

```bash
uv run uvicorn backend.main:app --reload   # bring-your-own-Postgres
```

## Docker / Compose

[`compose.yml`](compose.yml) defines a single Postgres 16 service (the app
itself runs on the host for a fast reload loop):

```bash
docker compose up -d        # start Postgres in the background
docker compose down         # stop it (data survives in the named volume)
docker compose down -v      # stop it AND wipe the data volume
```

## Environment variables

Config is loaded from the environment and an optional `.env` file
(`backend/core/config.py`). Copy [`.env.example`](.env.example) to `.env` to
customise. Every var has a working default, so an untouched copy runs against
the default compose Postgres out of the box.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/conduit` | SQLAlchemy connection URL (driver auto-normalised to asyncpg). |
| `CONDUIT_JWT_SECRET` | `dev-insecure-change-me-...` | JWT signing secret. **Override in any non-dev environment.** |
| `CONDUIT_DEBUG` | `false` | Verbose SQL echo + FastAPI debug mode. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `conduit` | Postgres container init (compose.yml) — keep in sync with `DATABASE_URL`. |
| `POSTGRES_PORT` | `5432` | Host port the Postgres container is published on. |

## Quality gates

```bash
make check                  # lint + format + tests
# or, à la carte:
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```

