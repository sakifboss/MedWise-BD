"""Row schemas for data/seed/*.json. Used by scripts/import_data.py to validate input.

Rows reference each other by name (not id) so that official data can replace
the sample files without any code changes.
"""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

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
    # Map data (pharmacies, areas): licence, fetch date and the area covered.
    licence: str | None = None
    fetched: date | None = None
    bbox_south_west_north_east: list[float] | None = None
    # What a fetch left out and why, and what the team still has to add.
    excluded: list[dict] = []
    to_add_by_team_gps: list[str] = []


StringentRegulator = Literal["US FDA", "UK MHRA", "EU GMP", "TGA Australia"]
STRINGENT_REGULATORS: tuple[str, ...] = ("US FDA", "UK MHRA", "EU GMP", "TGA Australia")


def _unique_regulators(values: list[str]) -> list[str]:
    """Deduplicate and keep the canonical order of STRINGENT_REGULATORS."""
    return [r for r in STRINGENT_REGULATORS if r in set(values)]


RegulatorList = Annotated[list[StringentRegulator], AfterValidator(_unique_regulators)]

UrlStr = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^https?://\S+$")]
UrlList = Annotated[list[UrlStr], AfterValidator(_unique_nonempty)]


class ManufacturerSeed(_SeedRow):
    name: NonEmptyStr
    years_active: int = Field(ge=0, le=200)
    export_countries: TextList = []
    export_country_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of export countries when names are not known (overrides list length)",
    )


class QualityFactorSeed(_SeedRow):
    manufacturer: NonEmptyStr
    stringent_approvals: RegulatorList = Field(
        default=[],
        description="Regulators that approved at least one of the company's plants",
    )
    regulated_market_exports: int = Field(ge=0, description="Number of regulated markets")
    compliance_score: float = Field(ge=0, le=100)
    recall_count: int = Field(ge=0)
    recall_data_available: bool = True
    market_share: float | None = Field(
        default=None, ge=0, le=100, description="Percent of national market; null if unknown"
    )
    source_urls: UrlList = []


class GenericSeed(_SeedRow):
    name: NonEmptyStr
    drug_class: NonEmptyStr
    indications: Annotated[TextList, Field(min_length=1)]
    dosage_forms: Annotated[list[DosageFormStr], Field(min_length=1)]
    side_effects: TextList = []
    precautions: TextList = []
    # What the source says about food, milk, alcohol and things to take apart, in its own words.
    # Empty when the source says nothing (the page then hides the section). Never doses.
    how_to_take: TextList = []
    source_urls: UrlList = Field(
        default=[], description="Pages the medicine information comes from"
    )
    # Reviewed Bangla translations, written by scripts/build_generics_bn.py. A field is either
    # absent (shown in English) or a complete line-by-line translation of the English field.
    drug_class_bn: NonEmptyStr | None = None
    indications_bn: list[NonEmptyStr] | None = None
    side_effects_bn: list[NonEmptyStr] | None = None
    precautions_bn: list[NonEmptyStr] | None = None
    how_to_take_bn: list[NonEmptyStr] | None = None

    @model_validator(mode="after")
    def _bangla_matches_english(self) -> "GenericSeed":
        for field in TRANSLATED_LIST_FIELDS:
            bangla = getattr(self, f"{field}_bn")
            if bangla is not None and len(bangla) != len(getattr(self, field)):
                raise ValueError(
                    f"{field}_bn has {len(bangla)} lines but {field} has "
                    f"{len(getattr(self, field))}; translate every line"
                )
        return self


TRANSLATED_LIST_FIELDS = ("indications", "side_effects", "precautions", "how_to_take")
TRANSLATED_FIELDS = ("drug_class", *TRANSLATED_LIST_FIELDS)


class BrandSeed(_SeedRow):
    name: NonEmptyStr
    generic: NonEmptyStr
    manufacturer: NonEmptyStr
    strength: StrengthStr
    dosage_form: DosageFormStr
    price_per_unit: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    source_url: UrlStr | None = Field(default=None, description="Where the price was taken from")


class InteractionSeed(_SeedRow):
    generic_a: NonEmptyStr
    generic_b: NonEmptyStr
    severity: Literal["minor", "moderate", "major"]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]
    description_bn: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)] | None
    ) = None


# ---------------------------------------------------------------- pharmacies (P9)

# Sylhet city: south, west, north, east. Pharmacies and areas must lie inside it.
SYLHET_BBOX = (24.86, 91.82, 24.95, 91.93)
PhoneStr = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{5,19}$")
]


def _inside_sylhet(lat: float, lon: float) -> None:
    south, west, north, east = SYLHET_BBOX
    if not (south <= lat <= north and west <= lon <= east):
        raise ValueError(f"({lat}, {lon}) is outside the Sylhet city area {SYLHET_BBOX}")


class PharmacySeed(_SeedRow):
    name: NonEmptyStr
    name_bn: NonEmptyStr | None = None
    lat: float
    lon: float
    address: NonEmptyStr | None = None
    phone: PhoneStr | None = None
    # "osm": from OpenStreetMap (its phone is public there); "survey": recorded on site by the team.
    source: Literal["osm", "survey"]
    osm_type: Literal["node", "way", "relation"] | None = None
    osm_id: int | None = Field(default=None, gt=0)
    surveyed_by: NonEmptyStr | None = None
    surveyed_on: date | None = None
    # Kept by hand: a partner who agreed (consent form kept by the team, never in the repo).
    is_partner: bool = False
    partner_since: date | None = None
    # Hide the number if the owner asks, with no code change.
    hide_phone: bool = False

    @model_validator(mode="after")
    def _check(self) -> "PharmacySeed":
        _inside_sylhet(self.lat, self.lon)
        if self.source == "osm" and (self.osm_type is None or self.osm_id is None):
            raise ValueError("an OpenStreetMap pharmacy needs osm_type and osm_id")
        if self.source == "survey" and (self.surveyed_by is None or self.surveyed_on is None):
            raise ValueError("a surveyed pharmacy needs surveyed_by and surveyed_on")
        if self.partner_since is not None and not self.is_partner:
            raise ValueError("partner_since is set but is_partner is false")
        return self

    @property
    def phone_shown(self) -> bool:
        """OSM numbers are public already; a survey number only for a partner who agreed."""
        if self.phone is None or self.hide_phone:
            return False
        return self.source == "osm" or self.is_partner


class AreaSeed(_SeedRow):
    name: NonEmptyStr
    name_bn: NonEmptyStr | None = None
    lat: float
    lon: float
    kind: NonEmptyStr
    osm: str | None = Field(default=None, pattern=r"^(node|way|relation)/\d+$")

    @model_validator(mode="after")
    def _check(self) -> "AreaSeed":
        _inside_sylhet(self.lat, self.lon)
        return self


# ---------------------------------------------------------------- symptom guide (P10)

# Group titles are UI text (dictionaries.ts); the items under them are NHS wording.
RedFlagGroup = Literal[
    "chest",
    "breathing",
    "face_arm_speech",
    "swelling_fainting",
    "seizure",
    "child_under_5",
    "age_5_and_over",
]
# Rules in the symptom guide depend on these; the import refuses a list without them.
REQUIRED_SPECIALTIES = ("general_medicine", "paediatrics", "obstetrics_gynaecology")
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None


class RedFlagSeed(_SeedRow):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+-\d+$")]
    group: RedFlagGroup
    text: NonEmptyStr
    text_bn: OptionalText = None
    # Only NHS pages that say to call 999 or go to A&E.
    source_url: Annotated[str, StringConstraints(pattern=r"^https://www\.nhs\.uk/\S+$")]


class SpecialtySeed(_SeedRow):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z_]+$")]
    name: NonEmptyStr
    name_bn: OptionalText = None
    covers: NonEmptyStr
    covers_bn: OptionalText = None
