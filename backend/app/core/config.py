import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'medwise.db').as_posix()}"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Tried in order when the main model is overloaded or unavailable (comma-separated).
    # Each model has its own free-tier quota, so more fallbacks = fewer 429s under bursts.
    gemini_fallback_models: str = (
        "gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.1-flash-lite,gemini-3.5-flash"
    )
    # Per model attempt; a hung model then falls through to the next one.
    gemini_timeout_seconds: float = 20.0
    # Don't start another model after this long (keeps the whole request bounded).
    gemini_total_seconds: float = 40.0
    max_upload_mb: float = 8.0
    # Protects the Gemini quota: per client per hour, and for everyone per day.
    prescription_limit_per_hour: int = 10
    prescription_limit_per_day: int = 300
    cors_origins: str = "http://localhost:3000"
    # Shared with the frontend (same value on Vercel and Render). When set, prescription uploads
    # must carry it, so only our website can spend the Gemini quota. Empty: no check (local dev).
    frontend_shared_secret: str = ""
    seed_dir: Path = REPO_DIR / "data" / "seed"

    @field_validator("gemini_api_key", "frontend_shared_secret")
    @classmethod
    def _clean_key(cls, key: str) -> str:
        """Drop whitespace/quotes that sneak in when pasting into hosting dashboards."""
        return key.strip().strip("'\"").strip()

    @property
    def version(self) -> str:
        """Deployed git commit (Render sets RENDER_GIT_COMMIT), or 'dev' locally."""
        return os.environ.get("RENDER_GIT_COMMIT", "dev")[:7]

    @property
    def gemini_models(self) -> list[str]:
        fallbacks = [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]
        return list(dict.fromkeys([self.gemini_model, *fallbacks]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
