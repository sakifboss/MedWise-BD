"""Row schemas for data/seed/*.json. Used by scripts/import_data.py to validate input.

Rows reference each other by name (not id) so that official data can replace
the sample files without any code changes.
"""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

_STRENGTH_PATTERN = re.compile(
    r"^\d+(\.\d+)? [a-z%]+(/\d+(\.\d+)? [a-z]+)?( \+ \d+(\.\d+)? [a-z%]+)*$"
)


def normalize_strength(value: str) -> str:
    """Canonical strength text: '500MG' -> '500 mg', '120mg / 5 mL' -> '120 mg/5 ml'."""
    text = value.strip().lower()
    text = re.sub(r"(\d)\s*([a-z%])", r"\1 \2", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s*\+\s*", " + ", text)
    return re.sub(r"\s+", " ", text)


def _check_strength(value: str) -> str:
    normalized = normalize_strength(value)
    if not _STRENGTH_PATTERN.match(normalized):
        raise ValueError(f"unrecognised strength format '{value}' (expected e.g. '500 mg')")
    return normalized


def normalize_dosage_form(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in values:
        cleaned = item.strip()
        if cleaned and cleaned.lower() not in seen:
            seen[cleaned.lower()] = cleaned
    return list(seen.values())


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
StrengthStr = Annotated[str, AfterValidator(_check_strength)]
DosageFormStr = Annotated[NonEmptyStr, AfterValidator(normalize_dosage_form)]
TextList = Annotated[list[str], AfterValidator(_unique_nonempty)]


class _SeedRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SeedMeta(_SeedRow):
    dataset: NonEmptyStr
    source: NonEmptyStr
    is_sample: bool
    sample_fields: list[str] = []
    note: str | None = None


class ManufacturerSeed(_SeedRow):
    name: NonEmptyStr
    years_active: int = Field(ge=0, le=200)
    export_countries: TextList = []


class QualityFactorSeed(_SeedRow):
    manufacturer: NonEmptyStr
    who_gmp: bool
    regulated_market_exports: int = Field(ge=0, description="Number of regulated markets")
    compliance_score: float = Field(ge=0, le=100)
    recall_count: int = Field(ge=0)
    market_share: float = Field(ge=0, le=100, description="Percent of national market")


class GenericSeed(_SeedRow):
    name: NonEmptyStr
    drug_class: NonEmptyStr
    indications: Annotated[TextList, Field(min_length=1)]
    dosage_forms: Annotated[list[DosageFormStr], Field(min_length=1)]
    side_effects: TextList = []
    precautions: TextList = []


class BrandSeed(_SeedRow):
    name: NonEmptyStr
    generic: NonEmptyStr
    manufacturer: NonEmptyStr
    strength: StrengthStr
    dosage_form: DosageFormStr
    price_per_unit: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class InteractionSeed(_SeedRow):
    generic_a: NonEmptyStr
    generic_b: NonEmptyStr
    severity: Literal["minor", "moderate", "major"]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]
