from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter, per_client_limit
from app.schemas.alternatives import DISCLAIMER, DISCLAIMER_BN
from app.schemas.common import Envelope, LangQuery
from app.schemas.interactions import (
    NO_RECORD_NOTE,
    NO_RECORD_NOTE_BN,
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


interactions_limiter = RateLimiter(get_settings().interactions_limit_per_minute, 60)


@router.post(
    "/interactions/check",
    response_model=Envelope[InteractionCheckResponse],
    dependencies=[Depends(per_client_limit(interactions_limiter))],
)
def check(
    body: InteractionCheckRequest,
    db: Annotated[Session, Depends(get_db)],
    lang: LangQuery = "en",
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
                    description=i.text(lang),
                )
                for i in report.interactions
            ],
            duplicates=[_medicine(g) for g in report.duplicates],
            pairs_checked=report.pairs_checked,
            note=NO_RECORD_NOTE_BN if lang == "bn" else NO_RECORD_NOTE,
            disclaimer=DISCLAIMER_BN if lang == "bn" else DISCLAIMER,
        )
    )
