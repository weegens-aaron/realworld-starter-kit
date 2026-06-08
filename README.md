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

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync --extra dev          # install deps into .venv (lockfile: uv.lock)
uv run uvicorn backend.main:app --reload
# -> http://127.0.0.1:8000  ·  health: GET /api/health
```

Quality gates:

```bash
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```

