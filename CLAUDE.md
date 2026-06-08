# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

Tooling is [uv](https://docs.astral.sh/uv/) (lockfile: `uv.lock`). Python 3.11+.

```bash
uv sync --extra dev                          # create/refresh .venv
uv run uvicorn backend.main:app --reload     # boot the app
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```

Frontend JS tests (vanilla, no bundler): `cd frontend && node --test`.

## Architecture Overview

A **single FastAPI application** serving both the JSON API and the HTML UI:

- `backend/` — `api` (routers, mounted at `/api`), `models` (SQLAlchemy 2.0),
  `services` (shared business logic), `core` (config/security). Entrypoint:
  `backend/main.py` (`create_app()` factory + `app`).
- `frontend/` — `templates` (Jinja2), `static` (vanilla JS, served at `/static`),
  `routes` (server-rendered HTML).

HTML routes call the service layer directly — no self-HTTP hop. See
`docs/adr/0001` for the HTMX + JWT-in-localStorage rendering strategy.

## Conventions & Patterns

- DRY/YAGNI/SOLID; keep files under ~600 lines; obey the Zen of Python.
- Config lives in `backend/core/config.py` (`get_settings()`); don't read
  `os.environ` directly.
- One router owns `/api`; one Jinja2 env (`frontend/templates_env.py`) owns
  templating and registers the shared avatar helpers.
