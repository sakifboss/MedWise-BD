"""One Gemini client for every feature that uses it (prescription reading, symptom guide).

It tries the configured models in order within a time budget, binds to IPv4 (some hosts hang on
Google's IPv6 address) and never logs request bodies, responses or the API key.
"""

import logging
import time

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Overloaded / rate-limited / model retired: worth trying the next model.
_TRY_NEXT_MODEL = {404, 429, 500, 503}


class GeminiUnavailable(Exception):
    """No model gave an answer. `status` is the last HTTP status (503 for network errors,
    400 when the answer had no text, e.g. a blocked request)."""

    def __init__(self, status: int, attempts: list[dict]) -> None:
        super().__init__(f"Gemini unavailable (last status {status})")
        self.status = status
        self.attempts = attempts


def response_text(payload: dict) -> str | None:
    """The text of the first candidate, or None (no candidates: e.g. a blocked request)."""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return None
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


class GeminiClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self.last_model: str | None = None  # which model answered the last call (for evaluation)
        self._client = client or httpx.Client(
            # Fail fast if a connection can't be opened; allow the model time to answer.
            timeout=httpx.Timeout(settings.gemini_timeout_seconds, connect=5.0),
            # Bind to IPv4: some hosts resolve Google's IPv6 address but silently drop
            # IPv6 traffic, which makes every request hang until the timeout.
            transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1),
        )

    def _post(self, model: str, body: dict) -> httpx.Response | str:
        """POST to one model; on timeout/network error return the error name instead."""
        try:
            return self._client.post(
                GEMINI_URL.format(model=model),
                headers={"x-goog-api-key": self._settings.gemini_api_key},
                json=body,
            )
        except httpx.HTTPError as exc:
            # The exception text holds the error only (no headers), so the key is not logged.
            logger.warning("Gemini request to %s failed: %s: %s", model, type(exc).__name__, exc)
            return type(exc).__name__

    def generate(self, body: dict) -> str:
        """The answer text of the first model that answers. Raises GeminiUnavailable."""
        started = time.monotonic()
        attempts: list[dict] = []
        last_status = 0
        for model in self._settings.gemini_models:
            if attempts and time.monotonic() - started > self._settings.gemini_total_seconds:
                break  # out of time budget: don't start another model
            t0 = time.monotonic()
            response = self._post(model, body)
            outcome = response if isinstance(response, str) else f"HTTP {response.status_code}"
            attempts.append(
                {"model": model, "result": outcome, "seconds": round(time.monotonic() - t0, 1)}
            )
            if isinstance(response, str):
                last_status = 503
                continue
            if response.status_code == 200:
                text = response_text(response.json())
                if text is None:
                    raise GeminiUnavailable(400, attempts)
                self.last_model = model
                return text
            # Log status only: the body may echo request details.
            logger.warning("Gemini %s returned HTTP %s", model, response.status_code)
            last_status = response.status_code
            if last_status not in _TRY_NEXT_MODEL:
                break
        raise GeminiUnavailable(last_status, attempts)
