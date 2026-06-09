#!/usr/bin/env bash
#
# dev.sh — one command to boot Conduit for local development.
#
# It does the boring-but-essential dance in order:
#   1. start the Postgres container (compose.yml) if it isn't already up;
#   2. wait until Postgres reports healthy (so we never race the DB);
#   3. apply database migrations (alembic upgrade head) — skipped gracefully
#      until the Alembic migration bead lands;
#   4. hand off to uvicorn with --reload.
#
# Usage:
#   ./scripts/dev.sh                 # full boot: db + migrate + uvicorn
#   ./scripts/dev.sh --no-db         # skip compose (you manage Postgres yourself)
#   ./scripts/dev.sh --no-migrate    # skip the migration step
#   PORT=8001 ./scripts/dev.sh       # serve on a different port
#
# Any extra args after the flags are forwarded to uvicorn (e.g. --workers 2).
#
# Env:
#   PORT          uvicorn port (default 8000).
#   HOST_BIND     uvicorn bind address (default 127.0.0.1).
#   WAIT_TIMEOUT  seconds to wait for Postgres health (default 60).

set -euo pipefail

# Resolve paths relative to THIS script so it runs from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

PORT="${PORT:-8000}"
HOST_BIND="${HOST_BIND:-127.0.0.1}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-60}"

# --- Parse our flags; everything else flows through to uvicorn ------------
START_DB=1
RUN_MIGRATIONS=1
UVICORN_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-db) START_DB=0 ;;
    --no-migrate) RUN_MIGRATIONS=0 ;;
    *) UVICORN_ARGS+=("$arg") ;;
  esac
done

# `uv run` is the project's blessed entrypoint (lockfile-pinned env). If it's
# missing, bail early with an actionable message rather than a cryptic failure.
if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' is not installed or not on PATH." >&2
  echo "       Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 127
fi

# --- 1 & 2. Postgres: start it, then wait until it's actually accepting ----
if [[ "${START_DB}" -eq 1 ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "error: 'docker' not found — install Docker or rerun with --no-db." >&2
    exit 127
  fi

  echo "==> Starting Postgres (docker compose up -d db) ..."
  docker compose up -d db

  echo "==> Waiting up to ${WAIT_TIMEOUT}s for Postgres to report healthy ..."
  deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
  until [[ "$(docker inspect -f '{{.State.Health.Status}}' conduit-postgres 2>/dev/null || echo starting)" == "healthy" ]]; do
    if [[ "$(date +%s)" -ge "${deadline}" ]]; then
      echo "error: Postgres did not become healthy within ${WAIT_TIMEOUT}s." >&2
      echo "       Check 'docker compose logs db'." >&2
      exit 1
    fi
    sleep 1
  done
  echo "==> Postgres is healthy."
fi

# --- 3. Migrations: alembic upgrade head (degrade gracefully pre-scaffold) -
if [[ "${RUN_MIGRATIONS}" -eq 1 ]]; then
  if [[ -f "alembic.ini" ]]; then
    echo "==> Applying migrations (alembic upgrade head) ..."
    uv run alembic upgrade head
  else
    echo "==> Skipping migrations: no alembic.ini yet (migration bead not landed)."
    echo "    The app boots against an empty schema until then; rerun once"
    echo "    Alembic is scaffolded. (--no-migrate silences this.)"
  fi
fi

# --- 4. Serve --------------------------------------------------------------
echo "==> Starting uvicorn on http://${HOST_BIND}:${PORT}  (health: /api/health)"
exec uv run uvicorn backend.main:app \
  --reload \
  --host "${HOST_BIND}" \
  --port "${PORT}" \
  ${UVICORN_ARGS[@]+"${UVICORN_ARGS[@]}"}
