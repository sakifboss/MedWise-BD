from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.models import Brand
from app.schemas.common import Envelope
from app.schemas.manufacturer import (
    FactorDetail,
    ManufacturerBrand,
    ManufacturerDetail,
    ManufacturerListItem,
)
from app.services.manufacturers import RatedManufacturer, factor_breakdown, rate_all, unknown_facts
from app.services.ranking import STRINGENT_REGULATORS

router = APIRouter(tags=["manufacturers"])


def _brand_counts(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Brand.manufacturer_id, func.count(Brand.id)).group_by(Brand.manufacturer_id)
    )
    return {manufacturer_id: count for manufacturer_id, count in rows}


@router.get("/manufacturers", response_model=Envelope[list[ManufacturerListItem]])
def list_manufacturers(
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[list[ManufacturerListItem]]:
    """Every manufacturer, highest quality score first."""
    counts = _brand_counts(db)
    return Envelope(
        data=[
            ManufacturerListItem(
                id=r.manufacturer.id,
                name=r.manufacturer.name,
                quality_score=round(100 * r.quality, 1),
                quality_rank=r.rank,
                stringent_approvals=list(r.manufacturer.stringent_approvals),
                brand_count=counts.get(r.manufacturer.id, 0),
            )
            for r in rate_all(db)
        ]
    )


def _detail(r: RatedManufacturer, total: int, brands: list[Brand]) -> ManufacturerDetail:
    m = r.manufacturer
    approved = list(m.stringent_approvals)
    return ManufacturerDetail(
        id=m.id,
        name=m.name,
        years_active=m.years_active,
        quality_score=round(100 * r.quality, 1),
        quality_rank=r.rank,
        manufacturer_count=total,
        stringent_approvals=approved,
        approvals_missing=[reg for reg in STRINGENT_REGULATORS if reg not in approved],
        export_country_count=m.export_country_count
        if m.export_country_count is not None
        else (len(m.export_countries) or None),
        export_countries=list(m.export_countries),
        regulated_market_exports=m.regulated_market_exports,
        compliance_score=m.compliance_score,
        recall_data_available=m.recall_data_available,
        recall_count=m.recall_count,
        market_share=m.market_share,
        factors=[
            FactorDetail(
                key=key,  # type: ignore[arg-type]
                weight=weight,
                score=round(score, 3),
                points=round(100 * weight * score, 1),
            )
            for key, weight, score in factor_breakdown(r.components)
        ],
        unknowns=unknown_facts(m),  # type: ignore[arg-type]
        source_urls=list(m.source_urls),
        brands=[
            ManufacturerBrand(
                id=b.id,
                name=b.name,
                generic_id=b.generic_id,
                generic_name=b.generic.name,
                strength=b.strength,
                dosage_form=b.dosage_form,
                price_per_unit=float(b.price_per_unit),
            )
            for b in brands
        ],
    )


@router.get("/manufacturers/{manufacturer_id}", response_model=Envelope[ManufacturerDetail])
def get_manufacturer(
    manufacturer_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[ManufacturerDetail]:
    """One manufacturer's quality score, explained factor by factor, with sources and brands."""
    rated = rate_all(db)
    match = next((r for r in rated if r.manufacturer.id == manufacturer_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Manufacturer {manufacturer_id} not found")
    brands = list(
        db.scalars(
            select(Brand)
            .options(joinedload(Brand.generic))
            .where(Brand.manufacturer_id == manufacturer_id)
        )
    )
    brands.sort(
        key=lambda b: (b.generic.name.casefold(), b.dosage_form, b.strength, b.name.casefold())
    )
    return Envelope(data=_detail(match, len(rated), brands))
