"""Application settings.

Single source of truth for runtime configuration. Values come from the
environment (and an optional ``.env`` file) so the same code runs in dev,
CI and prod without edits. Downstream beads (db, jwt, cors) read their
slice of config from here rather than touching ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so we parse the environment once. FastAPI dependencies and the
    app factory both call this; the ``lru_cache`` keeps it cheap and lets
    tests override via ``get_settings.cache_clear()`` when needed.
    """
    return Settings()
