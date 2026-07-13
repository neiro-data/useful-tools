"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the time-tracker app.

    Values are read from environment variables (prefixed with ``TIME_TRACKER_``) and, if present,
    a local ``.env`` file. Defaults are suitable for local, offline-first development.
    """

    model_config = SettingsConfigDict(
        env_prefix="TIME_TRACKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite is the canonical local data store.
    database_path: str = "time_tracker.db"

    # CORS: the React SPA will run on a localhost dev server.
    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # General app defaults (placeholders for future features).
    app_name: str = "Time Tracker"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
