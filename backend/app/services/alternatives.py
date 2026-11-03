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
        stringent_approvals=tuple(m.stringent_approvals or ()),
        export_countries=m.export_country_total,
        regulated_market_exports=m.regulated_market_exports,
        compliance_score=m.compliance_score,
        recall_count=m.recall_count,
        market_share=m.market_share,
        years_active=m.years_active,
        recall_data_available=m.recall_data_available,
        source_urls=tuple(m.source_urls or ()),
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
        price_source_url=b.source_url,
    )


def load_bounds(db: Session) -> Bounds:
    return compute_bounds(to_factors(m) for m in db.scalars(select(Manufacturer)))


def comparable_brands(db: Session, generic_id: int, strength: str, dosage_form: str) -> list[Brand]:
    """Brands with the same generic, strength and dosage form."""
    query = (
        select(Brand)
        .options(joinedload(Brand.manufacturer))
        .where(
            Brand.generic_id == generic_id,
            Brand.strength == strength,
            Brand.dosage_form == dosage_form,
        )
    )
    return list(db.scalars(query))


def rank_group(
    db: Session, generic_id: int, strength: str, dosage_form: str, lang: str = "en"
) -> list[RankedBrand]:
    brands = comparable_brands(db, generic_id, strength, dosage_form)
    if not brands:
        return []
    return rank_brands([to_candidate(b) for b in brands], load_bounds(db), lang)


def find_alternatives(db: Session, brand_id: int, lang: str = "en") -> AlternativesResult | None:
    brand = db.get(Brand, brand_id, options=[joinedload(Brand.generic)])
    if brand is None:
        return None
    ranked = rank_group(db, brand.generic_id, brand.strength, brand.dosage_form, lang)
    return AlternativesResult(selected=brand, ranked=ranked)
