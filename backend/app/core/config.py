from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'medwise.db').as_posix()}"
    gemini_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    seed_dir: Path = REPO_DIR / "data" / "seed"


@lru_cache
def get_settings() -> Settings:
    return Settings()
