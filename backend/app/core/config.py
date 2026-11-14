import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


def _model_list(first: str, fallbacks: str) -> list[str]:
    """The first model, then the comma-separated fallbacks, without repeats."""
    rest = [m.strip() for m in fallbacks.split(",") if m.strip()]
    return list(dict.fromkeys([first.strip(), *rest]))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'medwise.db').as_posix()}"
    # OpenAI (prescription reading and the symptom guide). Paid API; set a monthly limit in the
    # OpenAI dashboard. The key lives only in backend/.env and on Render, never in git.
    openai_api_key: str = ""
    # Symptom guide (text): the cheapest model is enough (13/13 red flags, 27/27 specialties).
    openai_model: str = "gpt-6-luna"
    # Tried in order when the main model is overloaded or unavailable (comma-separated).
    openai_fallback_models: str = "gpt-6.1-terra"
    # Prescription photos: handwriting needs the stronger model (real handwritten recall 94.1%
    # against 70.6% for gpt-6-luna; data/eval/results.md, results_gpt-6-luna.md); ~$0.003 a scan.
    openai_ocr_model: str = "gpt-6.1-terra"
    openai_ocr_fallback_models: str = "gpt-6-luna"
    # "none" to "max" on the gpt-6 models; empty leaves it to the model's default.
    openai_reasoning_effort: str = "low"
    openai_max_output_tokens: int = 2000
    # Per model attempt; a hung model then falls through to the next one.
    openai_timeout_seconds: float = 30.0
    # Don't start another model after this long (keeps the whole request bounded).
    openai_total_seconds: float = 60.0
    max_upload_mb: float = 8.0
    # Protects the OpenAI budget: per client per hour, and for everyone per day.
    prescription_limit_per_hour: int = 10
    prescription_limit_per_day: int = 300
    # Per client per minute; far above what a person typing or clicking needs.
    search_limit_per_minute: int = 120
    interactions_limit_per_minute: int = 60
    # "Request this medicine": per client, and a cap for everyone so nobody can fill the table.
    request_limit_per_hour: int = 10
    request_limit_per_day: int = 1000
    # "Report a problem" with a brand's data: same limits as the request log.
    report_limit_per_hour: int = 10
    report_limit_per_day: int = 1000
    # Symptom guide (OpenAI): per client per hour, and for everyone per day.
    symptom_limit_per_hour: int = 10
    symptom_limit_per_day: int = 200
    # Words that make the guide drop an AI-written note (diagnosis words), editable without code.
    symptom_words_path: Path = BACKEND_DIR / "app" / "core" / "symptom_words.json"
    # Doctor accounts (R2): sign-ups (and password resets) per client per hour.
    doctor_signup_limit_per_hour: int = 5
    # Rx Pad QR codes (R4): HMAC key, only in backend/.env and on Render; empty = QR signing off.
    # Changing it makes old QR codes show "Could not check" (they still open).
    rx_signing_secret: str = ""
    rx_sign_limit_per_day: int = 300  # per doctor
    rx_verify_limit_per_minute: int = 30  # per client
    # The only Origins allowed to change doctor data: the live site and local development or Docker.
    # Not Vercel previews (they use the production API and database). Not secret.
    site_origins: str = "https://medwise-bd.vercel.app,http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    # Shared with the frontend (same value on Vercel and Render). When set, prescription uploads
    # must carry it, so only our website can spend the OpenAI budget. Empty: no check (local dev).
    frontend_shared_secret: str = ""
    seed_dir: Path = REPO_DIR / "data" / "seed"
    # Answers built only from the medicine catalog are kept in memory this long (seconds; 0 = off).
    # The catalog changes only when import_data.py runs, before the server starts on each deploy.
    catalog_cache_seconds: int = 3600

    @field_validator("openai_api_key", "frontend_shared_secret", "rx_signing_secret")
    @classmethod
    def _clean_key(cls, key: str) -> str:
        """Drop whitespace/quotes that sneak in when pasting into hosting dashboards."""
        return key.strip().strip("'\"").strip()

    @property
    def version(self) -> str:
        """Deployed git commit (Render sets RENDER_GIT_COMMIT), or 'dev' locally."""
        return os.environ.get("RENDER_GIT_COMMIT", "dev")[:7]

    @property
    def openai_models(self) -> list[str]:
        return _model_list(self.openai_model, self.openai_fallback_models)

    @property
    def openai_ocr_models(self) -> list[str]:
        return _model_list(self.openai_ocr_model, self.openai_ocr_fallback_models)


@lru_cache
def get_settings() -> Settings:
    return Settings()
