"""Reads medicine names and strengths from a prescription photo using Gemini vision.

Safety rules (CLAUDE.md):
- The model ONLY extracts names + strengths. The response schema has no field for dosage,
  frequency, indications or advice, and anything else the model returns is discarded.
- Images are passed through in memory and never written to disk or logged.
"""

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.services.gemini import GeminiClient, GeminiUnavailable

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


class GeminiExtractor(GeminiClient):
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.gemini_api_key:
            raise AppError(503, "ocr_unavailable", "Prescription reading is not configured.")
        super().__init__(settings, client)

    def __call__(self, image: bytes, mime_type: str) -> list[ExtractedMedicine]:
        try:
            return parse_medicines(self.generate(_request_body(image, mime_type)))
        except GeminiUnavailable as exc:
            # Attempt details (model, outcome, time) help diagnose failures; they hold no secrets.
            if exc.status == 429:
                raise AppError(
                    429,
                    "ocr_busy",
                    "Too many prescriptions right now. Try again soon.",
                    exc.attempts,
                ) from exc
            if exc.status == 400:
                raise AppError(
                    502, "ocr_failed", "The prescription could not be read.", exc.attempts
                ) from exc
            raise AppError(
                503, "ocr_unavailable", "Prescription reading is unavailable.", exc.attempts
            ) from exc
