"""Loads comparable brands from the database and ranks them with services/ranking.py."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Brand, Manufacturer
from app.services.ranking import (
    Bounds,
    BrandCandidate,
    ManufacturerFactors,
    RankedBrand,
    compute_bounds,
    rank_brands,
)


@dataclass(frozen=True)
class AlternativesResult:
    selected: Brand
    ranked: list[RankedBrand]


def to_factors(m: Manufacturer) -> ManufacturerFactors:
    return ManufacturerFactors(
        id=m.id,
        name=m.name,
        who_gmp=m.who_gmp,
        export_countries=len(m.export_countries),
        regulated_market_exports=m.regulated_market_exports,
        compliance_score=m.compliance_score,
        recall_count=m.recall_count,
        market_share=m.market_share,
        years_active=m.years_active,
    )


def to_candidate(b: Brand) -> BrandCandidate:
    return BrandCandidate(
        brand_id=b.id,
        name=b.name,
        generic_id=b.generic_id,
        strength=b.strength,
        dosage_form=b.dosage_form,
        price_per_unit=b.price_per_unit,
        manufacturer=to_factors(b.manufacturer),
    )


def load_bounds(db: Session) -> Bounds:
    return compute_bounds(to_factors(m) for m in db.scalars(select(Manufacturer)))


def comparable_brands(db: Session, brand: Brand) -> list[Brand]:
    """Brands with the same generic, strength and dosage form (including `brand`)."""
    query = (
        select(Brand)
        .options(joinedload(Brand.manufacturer))
        .where(
            Brand.generic_id == brand.generic_id,
            Brand.strength == brand.strength,
            Brand.dosage_form == brand.dosage_form,
        )
    )
    return list(db.scalars(query))


def find_alternatives(db: Session, brand_id: int) -> AlternativesResult | None:
    brand = db.get(Brand, brand_id, options=[joinedload(Brand.generic)])
    if brand is None:
        return None
    candidates = [to_candidate(b) for b in comparable_brands(db, brand)]
    return AlternativesResult(selected=brand, ranked=rank_brands(candidates, load_bounds(db)))
