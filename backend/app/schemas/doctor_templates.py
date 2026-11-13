"""Doctor templates and favourite tests (R5). Only medicine lines, tests and advice: no patient
fields exist here at all."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import MAX_FAVOURITE_TESTS

MAX_TEMPLATE_LINES = 12
UNITS = Literal["tablet", "capsule", "spoon", "ml", "drop", "puff", "application"]
FOODS = Literal["", "before", "after", "with", "any"]


# "" none, "c" continue, or 1-365 days / weeks / months ("5d", "2w", "1m"), as in the QR payload.
def _at_most_365(code: str) -> str:
    if code not in ("", "c") and int(code[:-1]) > 365:
        raise ValueError("at most 365")
    return code


DurationCode = Annotated[
    str, StringConstraints(pattern=r"^(|c|[1-9]\d{0,2}[dwm])$"), AfterValidator(_at_most_365)
]


def _collapse(value: str) -> str:
    return " ".join(value.split())


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
    AfterValidator(_collapse),
]


def _test_names(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        cleaned = " ".join(value.split())
        if cleaned and cleaned.casefold() not in {v.casefold() for v in out}:
            out.append(cleaned)
    return out


class TemplateLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["brand", "generic", "free"]
    code: Annotated[str, StringConstraints(pattern=r"^BR\d{5}$")] | None = None  # brand lines
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    generic: Annotated[str, Field(max_length=200)] = ""
    strength: Annotated[str, Field(max_length=50)] = ""
    dosage_form: Annotated[str, Field(max_length=50)] = ""
    form_word: Annotated[str, Field(max_length=12)] = ""
    pattern: Annotated[str, Field(max_length=40)] = ""
    unit: UNITS = "tablet"
    food: FOODS = ""
    duration: DurationCode = ""
    substitution: bool = False
    note: Annotated[str, Field(max_length=120)] = ""


class TemplateLineOut(TemplateLine):
    # True when the brand is no longer in MedWise: the line is shown as written, with a note.
    gone: bool = False


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    lines: Annotated[list[TemplateLine], Field(max_length=MAX_TEMPLATE_LINES)]
    tests: Annotated[str, Field(max_length=1000)] = ""
    advice: Annotated[str, Field(max_length=2000)] = ""


class TemplateRename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class TemplateSummary(BaseModel):
    id: int
    name: str
    line_count: int
    updated_at: datetime


class TemplateOut(BaseModel):
    id: int
    name: str
    lines: list[TemplateLineOut]
    tests: str
    advice: str
    updated_at: datetime


class FavouriteTests(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tests: Annotated[
        list[Annotated[str, StringConstraints(max_length=80)]],
        Field(max_length=MAX_FAVOURITE_TESTS),
        AfterValidator(_test_names),
    ]
