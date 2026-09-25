from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.alternatives import (
    AlternativesResponse,
    GenericRef,
    ManufacturerSummary,
    QualityBreakdown,
    RankedAlternative,
)
from app.schemas.common import Envelope
from app.services.alternatives import find_alternatives
from app.services.ranking import RankedBrand

router = APIRouter(tags=["alternatives"])


def _to_schema(item: RankedBrand, selected_id: int) -> RankedAlternative:
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
    return Envelope(
        data=AlternativesResponse(
            selected_brand_id=brand.id,
            generic=GenericRef(id=brand.generic.id, name=brand.generic.name),
            strength=brand.strength,
            dosage_form=brand.dosage_form,
            alternatives=[_to_schema(item, brand.id) for item in result.ranked],
        )
    )
