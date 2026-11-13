"""Turns extracted prescription text into database options the user must confirm.

Nothing here decides for the user: every extracted medicine comes back with candidate
matches, and the frontend asks the user to pick (or reject) each one before any results.
"""

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Brand
from app.schemas.seed import normalize_strength
from app.services.ocr import ExtractedMedicine
from app.services.search import SearchHit, search_catalog

MAX_OPTIONS = 6
SUGGEST_MIN_SCORE = 85.0
GENERIC_MIN_SCORE = 80.0


@dataclass(frozen=True)
class MatchOption:
    kind: Literal["brand", "generic"]
    generic_id: int
    generic_name: str
    name: str
    strength: str
    dosage_form: str
    score: float
    strength_matches: bool
    brand_id: int | None = None
    manufacturer: str | None = None
    brand_code: str | None = None


@dataclass
class PrescriptionMatch:
    extracted: ExtractedMedicine
    options: list[MatchOption] = field(default_factory=list)
    suggested_index: int | None = None


def _same_strength(extracted: str | None, strength: str) -> bool:
    return extracted is not None and normalize_strength(extracted) == strength


def _brand_option(hit: SearchHit, extracted_strength: str | None) -> MatchOption:
    assert hit.strength is not None and hit.dosage_form is not None
    return MatchOption(
        kind="brand",
        generic_id=hit.generic_id,
        generic_name=hit.generic_name,
        name=hit.name,
        strength=hit.strength,
        dosage_form=hit.dosage_form,
        score=hit.score,
        strength_matches=_same_strength(extracted_strength, hit.strength),
        brand_id=hit.id,
        manufacturer=hit.manufacturer,
        brand_code=hit.code,
    )


def _generic_options(
    db: Session, hit: SearchHit, extracted_strength: str | None
) -> list[MatchOption]:
    """One option per strength + form of a generic written on the prescription."""
    presentations = db.execute(
        select(Brand.strength, Brand.dosage_form)
        .where(Brand.generic_id == hit.id)
        .distinct()
        .order_by(Brand.dosage_form, Brand.strength)
    )
    return [
        MatchOption(
            kind="generic",
            generic_id=hit.id,
            generic_name=hit.name,
            name=hit.name,
            strength=strength,
            dosage_form=form,
            score=hit.score,
            strength_matches=_same_strength(extracted_strength, strength),
        )
        for strength, form in presentations
    ]


def match_medicine(db: Session, medicine: ExtractedMedicine) -> PrescriptionMatch:
    _, hits = search_catalog(db, medicine.name, limit=15)
    options: list[MatchOption] = []
    for hit in hits:
        if hit.type == "brand":
            options.append(_brand_option(hit, medicine.strength))
        elif hit.score >= GENERIC_MIN_SCORE:
            options.extend(_generic_options(db, hit, medicine.strength))

    # Exact strength first, then closest name; on a tie, the name exactly as written wins
    # ("Cefixime" is the generic, "Cefixim" a brand of it).
    written = " ".join(medicine.name.split()).casefold()
    options.sort(
        key=lambda o: (
            not o.strength_matches,
            -o.score,
            o.name.casefold() != written,
            o.name.casefold(),
        )
    )
    options = options[:MAX_OPTIONS]

    suggested = None
    if options and options[0].score >= SUGGEST_MIN_SCORE:
        top = options[0]
        if medicine.strength is None or top.strength_matches:
            suggested = 0
    return PrescriptionMatch(extracted=medicine, options=options, suggested_index=suggested)


def match_prescription(db: Session, medicines: list[ExtractedMedicine]) -> list[PrescriptionMatch]:
    return [match_medicine(db, m) for m in medicines]
