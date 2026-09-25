"""Reads medicine names and strengths from a prescription photo using Gemini vision.

Safety rules (CLAUDE.md):
- The model ONLY extracts names + strengths. The response schema has no field for dosage,
  frequency, indications or advice, and anything else the model returns is discarded.
- Images are passed through in memory and never written to disk or logged.
"""

import base64
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_MEDICINES = 20

SYSTEM_PROMPT = """\
You transcribe medicine names from photos of prescriptions written in Bangladesh.

Return ONLY:
- name: the medicine name exactly as written (brand or generic), without prefixes such as
  "Tab.", "Cap.", "Syp." or "Inj."
- strength: the strength if written (e.g. "500 mg", "20 mg", "120 mg/5 ml"), otherwise null

Rules:
- Do NOT return dosage instructions, frequency (e.g. 1+0+1), duration, meal timing,
  diagnoses, patient details, doctor details or any advice.
- Do not guess medicines that are not written. If a name is hard to read, give your best
  reading of the letters as written.
- If the image is not a prescription or no medicine is legible, return an empty list.
"""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "medicines": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "strength": {"type": "STRING", "nullable": True},
                },
                "required": ["name"],
            },
        }
    },
    "required": ["medicines"],
}


@dataclass(frozen=True)
class ExtractedMedicine:
    name: str
    strength: str | None


class _ModelMedicine(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    strength: str | None = Field(default=None, max_length=50)


class _ModelOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    medicines: list[dict] = []


Extractor = Callable[[bytes, str], list[ExtractedMedicine]]


def _request_body(image: bytes, mime_type: str) -> dict:
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image).decode("ascii"),
                        }
                    },
                    {"text": "List the medicines on this prescription."},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }


def _response_text(payload: dict) -> str:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        # No candidates: e.g. the request was blocked (promptFeedback.blockReason).
        raise AppError(502, "ocr_failed", "The prescription could not be read.") from exc
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


def parse_medicines(text: str) -> list[ExtractedMedicine]:
    """Validate model JSON. Keeps only name + strength; drops invalid or duplicate rows."""
    try:
        output = _ModelOutput.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AppError(502, "ocr_failed", "The prescription could not be read.") from exc

    medicines: list[ExtractedMedicine] = []
    seen: set[tuple[str, str | None]] = set()
    for raw in output.medicines:
        try:
            item = _ModelMedicine.model_validate(raw)
        except ValidationError:
            continue
        strength = item.strength or None
        key = (item.name.casefold(), strength.casefold() if strength else None)
        if key not in seen:
            seen.add(key)
            medicines.append(ExtractedMedicine(item.name, strength))
    return medicines[:MAX_MEDICINES]


# Overloaded / rate-limited / model retired: worth trying the next model.
_TRY_NEXT_MODEL = {404, 429, 500, 503}


class GeminiExtractor:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.gemini_api_key:
            raise AppError(503, "ocr_unavailable", "Prescription reading is not configured.")
        self._settings = settings
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

    def __call__(self, image: bytes, mime_type: str) -> list[ExtractedMedicine]:
        body = _request_body(image, mime_type)
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
                return parse_medicines(_response_text(response.json()))
            # Log status only: the body may echo request details.
            logger.warning("Gemini %s returned HTTP %s", model, response.status_code)
            last_status = response.status_code
            if last_status not in _TRY_NEXT_MODEL:
                break

        # Attempt details (model, outcome, time) help diagnose failures; they hold no secrets.
        if last_status == 429:
            raise AppError(
                429, "ocr_busy", "Too many prescriptions right now. Try again soon.", attempts
            )
        if last_status == 400:
            raise AppError(502, "ocr_failed", "The prescription could not be read.", attempts)
        raise AppError(503, "ocr_unavailable", "Prescription reading is unavailable.", attempts)
