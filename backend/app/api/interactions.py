from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import Envelope
from app.schemas.interactions import (
    CheckedMedicine,
    GenericRef,
    InteractionCheckRequest,
    InteractionCheckResponse,
    InteractionOut,
)
from app.services.interactions import CheckedGeneric, check_interactions

router = APIRouter(tags=["interactions"])


def _medicine(g: CheckedGeneric) -> CheckedMedicine:
    return CheckedMedicine(generic_id=g.id, generic_name=g.name, brands=g.brands)


@router.post("/interactions/check", response_model=Envelope[InteractionCheckResponse])
def check(
    body: InteractionCheckRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Envelope[InteractionCheckResponse]:
    """Recorded interactions between any of the given brands/generics, most severe first.

    Also lists generics that were chosen through more than one brand (duplicate medicine).
    """
    report = check_interactions(db, body.generic_ids, body.brand_ids)
    return Envelope(
        data=InteractionCheckResponse(
            medicines=[_medicine(g) for g in report.medicines],
            interactions=[
                InteractionOut(
                    generic_a=GenericRef(id=i.generic_a.id, name=i.generic_a.name),
                    generic_b=GenericRef(id=i.generic_b.id, name=i.generic_b.name),
                    severity=i.severity,  # type: ignore[arg-type]
                    description=i.description,
                )
                for i in report.interactions
            ],
            duplicates=[_medicine(g) for g in report.duplicates],
            pairs_checked=report.pairs_checked,
        )
    )
