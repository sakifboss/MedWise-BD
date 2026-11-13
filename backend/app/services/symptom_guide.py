"""Symptom guide: which kind of doctor to start with, and a short note for that doctor.

Safety rules (Claude.MD, P10):
- The emergency checklist comes first and needs no AI; this service runs only after it.
- The model gets only the person's text and answers. It must not diagnose, name a disease or a
  medicine, or suggest a dose; it may only pick a specialty from our list.
- Its answer must match a strict schema (extra keys forbidden). An invalid answer or an unknown
  specialty gives the fallback: a general medicine specialist and a note built from the person's
  own answers. A note that names a catalog medicine, a dose or a diagnosis word is dropped too.
- The model can add an emergency warning (red_flag_suspected), never remove one.
- Fixed rules win over the model: a child goes to paediatrics, a pregnancy to obstetrics.
- Nothing the person wrote is stored or logged.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationError
from rapidfuzz import fuzz

from app.schemas.symptom_guide import DoctorNote, ModelAnswer, SymptomGuideIn
from app.services.llm import LlmUnavailable, strict_format
from app.services.transliterate import phonetic_key, to_latin

FALLBACK_SPECIALTY = "general_medicine"
CHILD_SPECIALTY = "paediatrics"
PREGNANCY_SPECIALTY = "obstetrics_gynaecology"

SINCE_LABELS = {
    "en": {
        "today": "Less than a day",
        "days": "1 to 6 days",
        "weeks": "1 to 4 weeks",
        "months": "More than a month",
    },
    "bn": {
        "today": "এক দিনের কম",
        "days": "১ থেকে ৬ দিন",
        "weeks": "১ থেকে ৪ সপ্তাহ",
        "months": "এক মাসের বেশি",
    },
}
_ANSWER_WORDS = {
    "severity": {"mild": "mild", "moderate": "moderate", "severe": "severe"},
    "age_group": {
        "child": "child (under 18)",
        "adult": "adult",
        "older_adult": "older adult (65+)",
    },
    "pregnant": {"yes": "yes", "no": "no", "not_applicable": "not applicable"},
}

# Doses, units and medicine forms (English, Banglish and Bangla).
DOSE_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(mg|mcg|µg|ml|g|iu|units?)\b"
    r"|\b(mg|mcg|ml|tablets?|tabs?|capsules?|caps?|syrups?|injections?|drops?|doses?|dosage|"
    r"puffs?|sachets?|ointments?|creams?|inhalers?|antibiotics?|painkillers?|medicines?|"
    r"medications?|pills?)\b"
    r"|\b(once|twice|thrice|one|two|three|four|\d+)\s*(times?|x)\s*(a|per|in a)?\s*(day|daily)\b"
    r"|\b(once|twice|thrice)\s+(a|per|in a)\s+(day|week)\b|\b(once|twice|thrice)\s+daily\b"
    r"|\b\d\s*\+\s*\d\s*\+\s*\d\b"  # 1+0+1, the way doses are written in Bangladesh
    r"|\b(bela|khaben|khabo|khete hobe)\b"
    r"|মিলিগ্রাম|মি\.গ্রা|এমজি|ট্যাবলেট|ক্যাপসুল|সিরাপ|ইনজেকশন|ড্রপ|ডোজ|ওষুধ|ঔষধ|বড়ি|"
    r"দিনে\s*[০-৯\d]+\s*(বার|বেলা)|[০-৯\d]+\s*বেলা",
    re.I,
)

Reason = Literal[
    "ok",
    "ai_unavailable",
    "invalid_answer",
    "unknown_specialty",
    "medicine_name",
    "dose",
    "diagnosis_word",
]


@dataclass(frozen=True)
class Words:
    diagnosis: re.Pattern[str]
    not_medicines: frozenset[str]


@lru_cache(maxsize=4)
def load_words(path: Path) -> Words:
    doc = json.loads(path.read_text(encoding="utf-8"))
    parts = []
    for word in doc["diagnosis_words"]:
        word = word.strip().casefold()
        if not word:
            continue
        prefix = word.endswith("*")
        stem = re.escape(word.rstrip("*"))
        if word.isascii():
            parts.append(rf"\b{stem}" + ("" if prefix else r"\b"))
        else:
            parts.append(stem)
    return Words(
        diagnosis=re.compile("|".join(parts), re.I),
        not_medicines=frozenset(w.casefold() for w in doc.get("not_medicine_words", [])),
    )


@dataclass
class GuideResult:
    emergency: bool
    specialty: str | None
    note: DoctorNote | None
    note_written_by: Literal["ai", "answers"] | None
    rule: Literal["child", "pregnant"] | None
    # Why the AI note or specialty was not used ("ok" when it was). For tests and evaluation only;
    # never shown, never logged with the person's text.
    reason: Reason = "ok"
    checks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- the prompt


def system_prompt(specialties: dict[str, str]) -> str:
    options = "\n".join(f"- {key}: {covers}" for key, covers in specialties.items())
    return f"""\
You help a person in Bangladesh decide which kind of doctor to see first. You are not a doctor.

Strict rules:
- Do NOT diagnose. Do NOT name any disease, illness, condition or infection, not even as a guess.
- Do NOT name any medicine, drug, brand, dose, treatment or test.
- Choose "specialty" ONLY from these ids:
{options}
  If you are unsure, choose "{FALLBACK_SPECIALTY}".
- Set "red_flag_suspected" to true if anything described could be an emergency (for example
  chest pain, severe difficulty breathing, sudden weakness of the face or an arm, slurred speech,
  a fit, fainting, heavy bleeding, a baby who is very unwell, or thoughts of self-harm), or if you
  are unsure. Otherwise false.
- "note" is a short note the person can show the doctor, using only what they told you, in plain
  words: "main_problem" (at most 120 characters), "duration" (at most 60 characters) and
  "other_symptoms" (at most 8 short phrases, each at most 60 characters). Describe what the person
  feels; never what it might be.
- Write the note in {{language}}.
- Return only JSON with exactly the keys specialty, red_flag_suspected and note.
"""


def response_schema(specialty_ids: list[str]) -> dict:
    """Strict-mode schema: every key required, no other keys, the specialty one of our ids.
    The server checks all of it again (lengths, ids, words) after the model answers."""
    return {
        "type": "object",
        "properties": {
            "specialty": {"type": "string", "enum": specialty_ids},
            "red_flag_suspected": {"type": "boolean"},
            "note": {
                "type": "object",
                "properties": {
                    "main_problem": {"type": "string"},
                    "duration": {"type": "string"},
                    "other_symptoms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["main_problem", "duration", "other_symptoms"],
                "additionalProperties": False,
            },
        },
        "required": ["specialty", "red_flag_suspected", "note"],
        "additionalProperties": False,
    }


def request_body(answers: SymptomGuideIn, specialties: dict[str, str]) -> dict:
    """What the model gets: our rules, and only the person's text and answers."""
    language = "Bangla" if answers.lang == "bn" else "English"
    person = {
        "what they wrote": answers.text,
        "since when": SINCE_LABELS["en"][answers.since],
        "how bad": _ANSWER_WORDS["severity"][answers.severity],
        "age group": _ANSWER_WORDS["age_group"][answers.age_group],
        "pregnant": _ANSWER_WORDS["pregnant"][answers.pregnant],
    }
    return {
        "instructions": system_prompt(specialties).replace("{language}", language),
        "content": [{"type": "input_text", "text": json.dumps(person, ensure_ascii=False)}],
        "text_format": strict_format("symptom_guide", response_schema(list(specialties))),
    }


# ---------------------------------------------------------------- checks on the note


def _words(text: str) -> list[str]:
    latin = to_latin(text).casefold()
    return re.findall(r"[a-z0-9][a-z0-9-]*", latin)


def names_medicine(text: str, catalog_names: list[str], not_medicines: frozenset[str]) -> bool:
    """True when the text contains a medicine or generic name from our catalog (Bangla too)."""
    words = [w for w in _words(text) if w not in not_medicines]
    candidates = words + [a + b for a, b in zip(words, words[1:], strict=False)]  # "max pro"
    for raw_name in catalog_names:
        name = re.sub(r"[^a-z0-9]", "", raw_name.casefold())
        if len(name) < 3 or name in not_medicines:
            continue
        name_key = phonetic_key(raw_name)
        for word in candidates:
            plain = word.replace("-", "")
            if plain == name:
                return True
            if len(plain) >= 5 and len(name) >= 5 and fuzz.ratio(plain, name) >= 88:
                return True
            if len(plain) >= 6 and name_key and phonetic_key(plain) == name_key:
                return True
    return False


def note_problem(
    note: DoctorNote, catalog_names: list[str], words: Words
) -> Literal["medicine_name", "dose", "diagnosis_word"] | None:
    text = " | ".join([note.main_problem, note.duration, *note.other_symptoms])
    if names_medicine(text, catalog_names, words.not_medicines):
        return "medicine_name"
    if DOSE_PATTERN.search(text):
        return "dose"
    if words.diagnosis.search(text):
        return "diagnosis_word"
    return None


def fallback_note(answers: SymptomGuideIn) -> DoctorNote:
    """The person's own words, without AI."""
    text = answers.text if len(answers.text) <= 120 else answers.text[:119].rstrip() + "…"
    return DoctorNote(
        main_problem=text,
        duration=SINCE_LABELS[answers.lang][answers.since],
        other_symptoms=[],
    )


# ---------------------------------------------------------------- the guide


def _red_flag_in(raw: object) -> bool:
    """The model's warning counts even when the rest of its answer is invalid."""
    return isinstance(raw, dict) and raw.get("red_flag_suspected") is True


def _rule(answers: SymptomGuideIn) -> tuple[str | None, Literal["child", "pregnant"] | None]:
    if answers.age_group == "child":
        return CHILD_SPECIALTY, "child"
    if answers.pregnant == "yes":
        return PREGNANCY_SPECIALTY, "pregnant"
    return None, None


def run_guide(
    answers: SymptomGuideIn,
    specialties: dict[str, str],
    catalog_names: list[str],
    words: Words,
    generate: Callable[[dict], str] | None,
) -> GuideResult:
    """`specialties` maps id -> what it covers (English); `generate` calls the model."""
    specialty, note, written_by, reason = (
        FALLBACK_SPECIALTY,
        fallback_note(answers),
        "answers",
        "ok",
    )
    emergency = False

    raw: object = None
    if generate is None:
        reason = "ai_unavailable"
    else:
        try:
            raw = json.loads(generate(request_body(answers, specialties)))
        except LlmUnavailable:
            reason = "ai_unavailable"
        except json.JSONDecodeError:
            reason = "invalid_answer"

    if raw is not None:
        emergency = _red_flag_in(raw)
        try:
            answer = ModelAnswer.model_validate(raw)
        except ValidationError:
            reason = "invalid_answer"
        else:
            if answer.specialty not in specialties:
                reason = "unknown_specialty"
            else:
                specialty = answer.specialty
                ai_note = DoctorNote(**answer.note.model_dump())
                problem = note_problem(ai_note, catalog_names, words)
                if problem:
                    reason = problem
                else:
                    note, written_by = ai_note, "ai"

    forced, rule = _rule(answers)
    if forced and forced in specialties:
        specialty = forced
    else:
        rule = None

    if emergency:
        return GuideResult(True, None, None, None, None, reason)
    return GuideResult(False, specialty, note, written_by, rule, reason)  # type: ignore[arg-type]
