from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Since = Literal["today", "days", "weeks", "months"]
Severity = Literal["mild", "moderate", "severe"]
AgeGroup = Literal["child", "adult", "older_adult"]
Pregnant = Literal["yes", "no", "not_applicable"]


class SymptomGuideIn(BaseModel):
    """What the person answered. Nothing here is stored or logged."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=3, max_length=1000, description="The problem in their own words")
    since: Since
    severity: Severity
    age_group: AgeGroup
    pregnant: Pregnant
    lang: Literal["en", "bn"] = "en"

    @field_validator("text")
    @classmethod
    def _tidy(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise ValueError("text is too short")
        return cleaned


class ModelNote(BaseModel):
    """The doctor note exactly as the model must return it; anything else is rejected."""

    model_config = ConfigDict(extra="forbid", strict=True)

    main_problem: str = Field(min_length=1, max_length=120)
    duration: str = Field(max_length=60)
    other_symptoms: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("other_symptoms")
    @classmethod
    def _short_items(cls, items: list[str]) -> list[str]:
        if any(len(item) > 60 or not item.strip() for item in items):
            raise ValueError("each other symptom must be 1 to 60 characters")
        return items


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    specialty: str
    red_flag_suspected: bool
    note: ModelNote


class DoctorNote(BaseModel):
    main_problem: str
    duration: str
    other_symptoms: list[str]


class SpecialtyOut(BaseModel):
    id: str
    name: str
    covers: str


class SymptomGuideOut(BaseModel):
    # True: show the emergency screen; the flow stops (no specialty, no note).
    emergency: bool
    specialty: SpecialtyOut | None
    note: DoctorNote | None
    # "ai": written by the model and checked; "answers": built from the person's own answers.
    note_written_by: Literal["ai", "answers"] | None
    # A fixed rule that chose the specialty: children -> paediatrics, pregnancy -> obstetrics.
    rule: Literal["child", "pregnant"] | None


class RedFlagOut(BaseModel):
    id: str
    group: str
    text: str
    source_url: str


class SymptomGuideSetup(BaseModel):
    red_flags: list[RedFlagOut]
    specialties: list[SpecialtyOut]
