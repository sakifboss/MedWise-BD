from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.db import get_db
from app.models import SEVERITIES, Brand, Generic, Interaction
from app.schemas.common import Envelope
from app.schemas.generic import GenericDetail, InteractionSummary, Presentation

router = APIRouter(tags=["generics"])


def _presentations(db: Session, generic_id: int) -> list[Presentation]:
    rows = db.execute(
        select(
            Brand.strength,
            Brand.dosage_form,
            func.count(Brand.id),
            func.min(Brand.price_per_unit),
            func.max(Brand.price_per_unit),
        )
        .where(Brand.generic_id == generic_id)
        .group_by(Brand.strength, Brand.dosage_form)
        .order_by(Brand.dosage_form, Brand.strength)
    )
    return [
        Presentation(
            strength=strength,
            dosage_form=form,
            brand_count=count,
            min_price=float(low),
            max_price=float(high),
        )
        for strength, form, count, low, high in rows
    ]


def _interactions(db: Session, generic_id: int) -> list[InteractionSummary]:
    other = aliased(Generic)
    other_id = case(
        (Interaction.generic_a_id == generic_id, Interaction.generic_b_id),
        else_=Interaction.generic_a_id,
    )
    rows = db.execute(
        select(other.id, other.name, Interaction.severity, Interaction.description)
        .join(other, other.id == other_id)
        .where(or_(Interaction.generic_a_id == generic_id, Interaction.generic_b_id == generic_id))
    )
    items = [
        InteractionSummary(generic_id=i, generic_name=n, severity=s, description=d)
        for i, n, s, d in rows
    ]
    items.sort(key=lambda x: (-SEVERITIES.index(x.severity), x.generic_name.casefold()))
    return items


@router.get("/generics/{generic_id}", response_model=Envelope[GenericDetail])
def get_generic(
    generic_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[GenericDetail]:
    generic = db.get(Generic, generic_id)
    if generic is None:
        raise HTTPException(status_code=404, detail=f"Generic {generic_id} not found")
    detail = GenericDetail(
        id=generic.id,
        name=generic.name,
        drug_class=generic.drug_class,
        indications=generic.indications,
        dosage_forms=generic.dosage_forms,
        side_effects=generic.side_effects,
        precautions=generic.precautions,
        source_urls=generic.source_urls,
        presentations=_presentations(db, generic_id),
        interactions=_interactions(db, generic_id),
    )
    return Envelope(data=detail)
