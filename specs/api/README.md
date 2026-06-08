# API Test Harness (Hurl)

Integration tests that hit the **running** Conduit backend over HTTP and
assert the [RealWorld API spec](https://realworld-docs.netlify.app/specifications/backend/endpoints/).
This is the harness the resource verify-tasks invoke.

## Layout

```
specs/api/
├── run-api-tests-hurl.sh   # the runner (this is the entrypoint)
├── README.md               # you are here
└── hurl/                   # one .hurl file per feature area, run in order
    ├── 00-health.hurl      # liveness (the only route green on the scaffold)
    ├── 01-auth.hurl        # register / login / current user / update
    ├── 02-profiles.hurl    # profile + follow / unfollow
    ├── 03-articles.hurl    # article CRUD + listing + tag filter
    ├── 04-comments.hurl    # add / list / delete comments
    ├── 05-favorites.hurl   # favorite / unfavorite
    └── 06-tags.hurl        # tags endpoint
```

## Running locally

Boot the app (against any Postgres) in one terminal:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/conduit \
  uv run uvicorn backend.main:app --port 8000
```

Then run the suite in another:

```bash
HOST=http://localhost:8000/api ./specs/api/run-api-tests-hurl.sh
```

`HOST` **must include the `/api` prefix** — every `.hurl` file references it
as `{{host}}` and the app mounts the JSON API under `/api`.

### Handy flags

```bash
# Run a single file
./specs/api/run-api-tests-hurl.sh specs/api/hurl/01-auth.hurl

# Skip the readiness poll (app is already up)
./specs/api/run-api-tests-hurl.sh --no-wait

# Forward any flag to hurl (e.g. verbose request/response dumps)
./specs/api/run-api-tests-hurl.sh --verbose

# Write JUnit + HTML reports (what CI does)
HURL_REPORT_DIR=./hurl-report ./specs/api/run-api-tests-hurl.sh
```

## Design notes

- **Self-contained files.** Each auth-requiring file registers its *own*
  fresh user inline (with a `{{newUuid}}` email), so the suite is
  re-runnable and parallel-safe — no shared fixtures, no teardown, no
  cross-file token plumbing.
- **Canonical RealWorld status codes.** Successful requests assert `200`
  across the board — including create/update/delete — to match the official
  RealWorld spec & its Postman conformance suite, rather than stricter REST
  `201`/`204`. Endpoint beads should target these codes.
- **Auth scheme is `Authorization: Token <jwt>`** — RealWorld's non-standard
  header, *not* `Bearer` (see `backend/core/deps.py`).
- **Expected to be red until endpoints land.** Only `00-health.hurl` passes
  on the bare scaffold; the rest go green as the feature beads ship their
  routers.

## CI

`.github/workflows/api-tests.yml` boots Postgres + the app and runs this
harness on every push/PR. It uploads the Hurl report as an artifact.

## Requirements

[Hurl](https://hurl.dev/docs/installation.html) on your `PATH`.
