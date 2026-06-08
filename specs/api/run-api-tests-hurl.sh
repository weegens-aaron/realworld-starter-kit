#!/usr/bin/env bash
#
# run-api-tests-hurl.sh — drive the Hurl API suite against a running Conduit.
#
# This is the harness the resource verify-tasks invoke: point it at a live
# backend and it runs every .hurl file under ./hurl/ as an integration test.
#
# Usage:
#   HOST=http://localhost:8000/api ./run-api-tests-hurl.sh
#   ./run-api-tests-hurl.sh --no-wait            # skip the readiness poll
#   ./run-api-tests-hurl.sh specs/api/hurl/01-auth.hurl   # a subset
#
# Any extra args after the flags are passed straight through to `hurl`
# (e.g. --verbose, or explicit file paths to run a subset).
#
# Env:
#   HOST           Base URL of the API, INCLUDING the /api prefix.
#                  Default: http://localhost:8000/api
#   WAIT_TIMEOUT   Seconds to wait for HOST/health before giving up. Default 30.
#   HURL_REPORT_DIR  If set, write JUnit + HTML reports there (handy in CI).
#
# Exit code is hurl's: 0 = all green, non-zero = at least one failure. The
# suite "may be red until endpoints land" — that's expected and intentional.

set -euo pipefail

# Resolve paths relative to THIS script so it works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HURL_DIR="${SCRIPT_DIR}/hurl"

HOST="${HOST:-http://localhost:8000/api}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-30}"

# --- Parse args: our own flags, hurl passthrough flags, explicit files ----
WAIT=1
HURL_FLAGS=()   # extra flags forwarded to hurl (e.g. --verbose)
HURL_FILES=()   # explicit .hurl files to run instead of the whole suite
for arg in "$@"; do
  case "$arg" in
    --no-wait) WAIT=0 ;;
    --*) HURL_FLAGS+=("$arg") ;;
    *) HURL_FILES+=("$arg") ;;
  esac
done

# --- Preconditions -------------------------------------------------------
if ! command -v hurl >/dev/null 2>&1; then
  echo "error: 'hurl' is not installed or not on PATH." >&2
  echo "       Install it: https://hurl.dev/docs/installation.html" >&2
  exit 127
fi

echo "==> Hurl $(hurl --version | head -n1)"
echo "==> Target HOST: ${HOST}"

# --- Wait for the app to answer its liveness probe -----------------------
# The health route lives at HOST/health (HOST already includes /api).
if [[ "${WAIT}" -eq 1 ]]; then
  echo "==> Waiting up to ${WAIT_TIMEOUT}s for ${HOST}/health ..."
  deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
  until curl --silent --fail --output /dev/null "${HOST}/health"; do
    if [[ "$(date +%s)" -ge "${deadline}" ]]; then
      echo "error: ${HOST}/health did not come up within ${WAIT_TIMEOUT}s." >&2
      exit 1
    fi
    sleep 1
  done
  echo "==> Backend is up."
fi

# --- Choose what to run --------------------------------------------------
# Explicit files given as args win; otherwise run the whole suite in order.
if [[ "${#HURL_FILES[@]}" -gt 0 ]]; then
  FILES=("${HURL_FILES[@]}")
else
  shopt -s nullglob
  FILES=("${HURL_DIR}"/*.hurl)
  shopt -u nullglob
  if [[ "${#FILES[@]}" -eq 0 ]]; then
    echo "error: no .hurl files found in ${HURL_DIR}" >&2
    exit 1
  fi
fi

# --- Optional CI reports -------------------------------------------------
REPORT_ARGS=()
if [[ -n "${HURL_REPORT_DIR:-}" ]]; then
  mkdir -p "${HURL_REPORT_DIR}"
  REPORT_ARGS+=(--report-junit "${HURL_REPORT_DIR}/junit.xml")
  REPORT_ARGS+=(--report-html "${HURL_REPORT_DIR}/html")
fi

# --- Run -----------------------------------------------------------------
# --test       : test mode (assertions enforced, summary printed).
# --variable   : inject the base URL the .hurl files reference as {{host}}.
echo "==> Running ${#FILES[@]} Hurl file(s) ..."
# The ${arr[@]+"${arr[@]}"} idiom expands to nothing when the array is empty,
# which keeps `set -u` happy on bash 3.2 (macOS) as well as modern bash.
exec hurl \
  --test \
  --variable "host=${HOST}" \
  ${REPORT_ARGS[@]+"${REPORT_ARGS[@]}"} \
  ${HURL_FLAGS[@]+"${HURL_FLAGS[@]}"} \
  "${FILES[@]}"
