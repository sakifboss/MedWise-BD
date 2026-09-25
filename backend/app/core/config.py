from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'medwise.db').as_posix()}"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Tried in order when the main model is overloaded or unavailable (comma-separated).
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3.5-flash"
    gemini_timeout_seconds: float = 45.0
    max_upload_mb: float = 8.0
    # Protects the Gemini quota: per client per hour, and for everyone per day.
    prescription_limit_per_hour: int = 10
    prescription_limit_per_day: int = 300
    cors_origins: str = "http://localhost:3000"
    seed_dir: Path = REPO_DIR / "data" / "seed"

    @property
    def gemini_models(self) -> list[str]:
        fallbacks = [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]
        return list(dict.fromkeys([self.gemini_model, *fallbacks]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
