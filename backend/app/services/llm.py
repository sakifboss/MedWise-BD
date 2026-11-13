"""One OpenAI client for every feature that uses a language model (prescription reading, symptom
guide), through the Responses API with a strict JSON schema.

It tries the configured models in order within a time budget, binds to IPv4 (some hosts hang on
IPv6), sends `store: false` (OpenAI keeps no copy of the response for later retrieval), and never
logs request bodies, responses or the API key. Called with httpx directly, so no extra dependency.
"""

import logging
import time
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

RESPONSES_URL = "https://api.openai.com/v1/responses"

# Overloaded / rate-limited / model not available to this key: worth trying the next model.
_TRY_NEXT_MODEL = {404, 429, 500, 502, 503}


class LlmUnavailable(Exception):
    """No model gave a usable answer. `status` is the last HTTP status: 503 for network errors,
    400 when the answer was refused, incomplete or had no text."""

    def __init__(self, status: int, attempts: list[dict]) -> None:
        super().__init__(f"Language model unavailable (last status {status})")
        self.status = status
        self.attempts = attempts


def strict_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """`text.format` for a strict JSON-schema answer."""
    return {"type": "json_schema", "name": name, "strict": True, "schema": schema}


def output_text(payload: dict) -> str | None:
    """The answer text, or None when the model refused, stopped early or returned no text."""
    if payload.get("status") not in (None, "completed"):
        return None
    texts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                return None
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
    return "".join(texts) or None


class LlmClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self.last_model: str | None = None  # which model answered the last call (for evaluation)
        self._client = client or httpx.Client(
            # Fail fast if a connection can't be opened; allow the model time to answer.
            timeout=httpx.Timeout(settings.openai_timeout_seconds, connect=5.0),
            # Bind to IPv4: some hosts resolve an IPv6 address but silently drop IPv6 traffic,
            # which makes every request hang until the timeout.
            transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=1),
        )

    def _body(
        self, model: str, instructions: str, content: list[dict], text_format: dict
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "text": {"format": text_format},
            "store": False,
            "max_output_tokens": self._settings.openai_max_output_tokens,
        }
        if self._settings.openai_reasoning_effort:
            body["reasoning"] = {"effort": self._settings.openai_reasoning_effort}
        return body

    def _post(self, body: dict) -> httpx.Response | str:
        """POST once; on timeout/network error return the error name instead."""
        try:
            return self._client.post(
                RESPONSES_URL,
                headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            # The exception text holds the error only (no headers), so the key is not logged.
            logger.warning("OpenAI request to %s failed: %s", body["model"], type(exc).__name__)
            return type(exc).__name__

    def generate(self, instructions: str, content: list[dict], text_format: dict) -> str:
        """The JSON text of the first model that answers. Raises LlmUnavailable."""
        started = time.monotonic()
        attempts: list[dict] = []
        last_status = 0
        for model in self._settings.openai_models:
            if attempts and time.monotonic() - started > self._settings.openai_total_seconds:
                break  # out of time budget: don't start another model
            t0 = time.monotonic()
            response = self._post(self._body(model, instructions, content, text_format))
            outcome = response if isinstance(response, str) else f"HTTP {response.status_code}"
            attempts.append(
                {"model": model, "result": outcome, "seconds": round(time.monotonic() - t0, 1)}
            )
            if isinstance(response, str):
                last_status = 503
                continue
            if response.status_code == 200:
                text = output_text(response.json())
                if text is None:
                    raise LlmUnavailable(400, attempts)
                self.last_model = model
                return text
            # Log status only: the body may echo request details.
            logger.warning("OpenAI %s returned HTTP %s", model, response.status_code)
            last_status = response.status_code
            if last_status not in _TRY_NEXT_MODEL:
                break
        raise LlmUnavailable(last_status, attempts)
