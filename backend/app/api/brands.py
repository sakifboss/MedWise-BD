"""Every brand in one small list, so a device can look brands up by code without asking the server
about a particular medicine (used to open old saved lists, and later by the /rx page)."""

from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.catalog_cache import catalog_cache
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter, per_client_limit
from app.models import Brand
from app.schemas.brand_index import BrandIndex, BrandIndexItem
from app.schemas.common import Envelope
from app.services.alternatives import load_bounds, to_candidate
from app.services.ranking import rank_brands

router = APIRouter(tags=["brands"])

index_limiter = RateLimiter(get_settings().search_limit_per_minute, 60)


@router.get(
    "/brands/index",
    response_model=Envelope[BrandIndex],
    dependencies=[Depends(per_client_limit(index_limiter))],
)
def brand_index(
    db: Annotated[Session, Depends(get_db)], response: Response
) -> Envelope[BrandIndex]:
    # The data changes only when a deploy re-imports the seed files.
    response.headers["Cache-Control"] = "public, max-age=3600"
    return catalog_cache.get_or_build(("brand-index",), lambda: _brand_index(db))


def _brand_index(db: Session) -> Envelope[BrandIndex]:
    brands = db.scalars(
        select(Brand)
        .options(joinedload(Brand.generic), joinedload(Brand.manufacturer))
        .order_by(Brand.code)
    ).all()
    groups: dict[tuple[int, str, str], list[Brand]] = defaultdict(list)
    for b in brands:
        groups[(b.generic_id, b.strength, b.dosage_form)].append(b)
    bounds = load_bounds(db)
    rank: dict[int, tuple[int, int]] = {}
    for members in groups.values():
        for item in rank_brands([to_candidate(b) for b in members], bounds, "en"):
            rank[item.candidate.brand_id] = (item.rank, len(members))
    items = [
        BrandIndexItem(
            code=b.code,
            id=b.id,
            name=b.name,
            generic_id=b.generic_id,
            generic=b.generic.name,
            strength=b.strength,
            dosage_form=b.dosage_form,
            manufacturer=b.manufacturer.name,
            price_per_unit=float(b.price_per_unit),
            price_checked_on=b.price_checked_on,
            rank=rank[b.id][0],
            group_size=rank[b.id][1],
            approvals=len(b.manufacturer.stringent_approvals or []),
        )
        for b in brands
    ]
    return Envelope(data=BrandIndex(brands=items))
