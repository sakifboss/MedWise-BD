"""Counts of what the catalog covers, so the UI never hard-codes them."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.catalog_cache import catalog_cache
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter, per_client_limit
from app.models import Brand, Generic, Interaction, Manufacturer
from app.schemas.common import Envelope
from app.schemas.medicine_request import CatalogStats

router = APIRouter(tags=["stats"])

stats_limiter = RateLimiter(get_settings().search_limit_per_minute, 60)


@router.get(
    "/stats",
    response_model=Envelope[CatalogStats],
    dependencies=[Depends(per_client_limit(stats_limiter))],
)
def catalog_stats(db: Annotated[Session, Depends(get_db)]) -> Envelope[CatalogStats]:
    def count(model: type) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    return catalog_cache.get_or_build(
        ("stats",),
        lambda: Envelope(
            data=CatalogStats(
                generics=count(Generic),
                brands=count(Brand),
                manufacturers=count(Manufacturer),
                interactions=count(Interaction),
            )
        ),
    )
