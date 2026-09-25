from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Generic
from app.schemas.alternatives import (
    AlternativesResponse,
    GenericRef,
    ManufacturerSummary,
    QualityBreakdown,
    RankedAlternative,
)
from app.schemas.common import Envelope
from app.schemas.seed import normalize_dosage_form, normalize_strength
from app.services.alternatives import find_alternatives, rank_group
from app.services.ranking import RankedBrand

router = APIRouter(tags=["alternatives"])


def _to_schema(item: RankedBrand, selected_id: int | None) -> RankedAlternative:
    c, m = item.candidate, item.candidate.manufacturer
    return RankedAlternative(
        rank=item.rank,
        brand_id=c.brand_id,
        name=c.name,
        manufacturer=ManufacturerSummary(id=m.id, name=m.name, who_gmp=m.who_gmp),
        price_per_unit=float(c.price_per_unit),
        final_score=round(item.final_score, 1),
        quality_score=round(item.quality_score, 3),
        price_score=round(item.price_score, 3),
        quality_breakdown=QualityBreakdown(
            **{k: round(v, 3) for k, v in item.components.__dict__.items()}
        ),
        reasons=item.reasons,
        is_selected=c.brand_id == selected_id,
    )


def _response(
    generic: Generic,
    strength: str,
    dosage_form: str,
    ranked: list[RankedBrand],
    selected_id: int | None = None,
) -> Envelope[AlternativesResponse]:
    return Envelope(
        data=AlternativesResponse(
            selected_brand_id=selected_id,
            generic=GenericRef(id=generic.id, name=generic.name),
            strength=strength,
            dosage_form=dosage_form,
            alternatives=[_to_schema(item, selected_id) for item in ranked],
        )
    )


@router.get("/alternatives/{brand_id}", response_model=Envelope[AlternativesResponse])
def get_alternatives(
    brand_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[AlternativesResponse]:
    """Same generic, same strength, same dosage form, ranked by quality (80%) and price (20%).

    The selected brand is included in the list (is_selected=true) so users can see where it stands.
    """
    result = find_alternatives(db, brand_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Brand {brand_id} not found")
    brand = result.selected
    return _response(brand.generic, brand.strength, brand.dosage_form, result.ranked, brand.id)


@router.get("/generics/{generic_id}/ranking", response_model=Envelope[AlternativesResponse])
def get_generic_ranking(
    generic_id: Annotated[int, Path(ge=1)],
    strength: Annotated[str, Query(min_length=1, max_length=50)],
    dosage_form: Annotated[str, Query(min_length=1, max_length=50)],
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[AlternativesResponse]:
    """Rank every brand of a generic at one strength and dosage form (no selected brand)."""
    generic = db.get(Generic, generic_id)
    if generic is None:
        raise HTTPException(status_code=404, detail=f"Generic {generic_id} not found")
    strength, dosage_form = normalize_strength(strength), normalize_dosage_form(dosage_form)
    ranked = rank_group(db, generic_id, strength, dosage_form)
    if not ranked:
        raise HTTPException(
            status_code=404,
            detail=f"No {generic.name} {strength} {dosage_form} brands found",
        )
    return _response(generic, strength, dosage_form, ranked)
