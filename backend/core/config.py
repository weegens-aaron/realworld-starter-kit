"""Application settings.

Single source of truth for runtime configuration. Values come from the
environment (and an optional ``.env`` file) so the same code runs in dev,
CI and prod without edits. Downstream beads (db, jwt, cors) read their
slice of config from here rather than touching ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application configuration.

    Only scaffold-level knobs live here for now; the db/jwt/cors beads will
    extend this model (DATABASE_URL, JWT_SECRET, allowed origins, ...).
    """

    model_config = SettingsConfigDict(
        env_prefix="CONDUIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Conduit"
    debug: bool = False

    # --- Database (read by backend.core.db) ------------------------------
    # The SQLAlchemy connection URL. We honour the de-facto-standard bare
    # ``DATABASE_URL`` (what Postgres hosts/Heroku/Fly/etc. inject) *and* the
    # project's ``CONDUIT_`` prefix, so deploy platforms work out of the box
    # without a rename. Whatever driver you pass is normalised to asyncpg in
    # backend.core.db, so ``postgres://``, ``postgresql://`` and
    # ``postgresql+asyncpg://`` all just work.
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/conduit",
        validation_alias=AliasChoices("DATABASE_URL", "CONDUIT_DATABASE_URL"),
    )

    # Where the static assets and templates live, relative to the repo root.
    # Kept here so the entrypoint and the templates env agree on one path.
    static_dir: str = "frontend/static"
    templates_dir: str = "frontend/templates"

    # --- JWT / auth knobs (read by backend.core.security) -----------------
    # The signing secret MUST be overridden in any non-dev environment via
    # CONDUIT_JWT_SECRET. The default is intentionally obvious so a leaked
    # token from a misconfigured deploy is easy to spot.
    jwt_secret: str = "dev-insecure-change-me-please-override-in-prod"
    jwt_algorithm: str = "HS256"
    # How long an issued access token stays valid, in minutes (default 7 days).
    jwt_expires_minutes: int = 60 * 24 * 7

    # --- CORS (read by backend.main.create_app) --------------------------
    # The browser frontends (e2e suite + demo SPA) hit this API from a
    # *different* origin, so cross-origin requests (and their OPTIONS preflight)
    # must be opted in via CORS or the browser blocks them. Auth is header-based
    # ("Authorization: Token <jwt>" out of localStorage), NOT cookie-based, so we
    # don't need credentialed CORS — which lets us keep the maximally permissive
    # "*" default. See docs/backend/cors.md. Override CONDUIT_CORS_ORIGINS
    # (comma-separated) to lock it down in prod.
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string *or* a real list from the env.

        pydantic-settings would otherwise demand JSON for a ``list`` field,
        which is a hostile UX for an env var. A bare ``"a.com,b.com"`` is what
        operators actually type, so we split it ourselves; anything else (an
        already-parsed list, the default) passes straight through.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so we parse the environment once. FastAPI dependencies and the
    app factory both call this; the ``lru_cache`` keeps it cheap and lets
    tests override via ``get_settings.cache_clear()`` when needed.
    """
    return Settings()
