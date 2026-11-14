"""Pharmacies in Sylhet city (OpenStreetMap, team survey). Real places only, no stock claims.

The whole list is small, so it is returned at once and the browser sorts by distance:
the user's location never reaches this server.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.catalog_cache import catalog_cache
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter, per_client_limit
from app.models import Area, Pharmacy
from app.schemas.common import Envelope
from app.schemas.pharmacy import AreaOut, PharmaciesResponse, PharmacyOut
from app.schemas.seed import SYLHET_BBOX

router = APIRouter(tags=["pharmacies"])

pharmacies_limiter = RateLimiter(get_settings().search_limit_per_minute, 60)


def _pharmacy(p: Pharmacy) -> PharmacyOut:
    return PharmacyOut(
        id=p.id,
        name=p.name,
        name_bn=p.name_bn,
        lat=p.lat,
        lon=p.lon,
        address=p.address,
        phone=p.phone,
        phone_from_osm=p.phone is not None and p.source == "osm",
        is_partner=p.is_partner,
    )


@router.get(
    "/pharmacies",
    response_model=Envelope[PharmaciesResponse],
    dependencies=[Depends(per_client_limit(pharmacies_limiter))],
)
def list_pharmacies(
    db: Annotated[Session, Depends(get_db)],
    city: Annotated[Literal["sylhet"], Query(description="Only Sylhet city for now")] = "sylhet",
) -> Envelope[PharmaciesResponse]:
    return catalog_cache.get_or_build(("pharmacies", city), lambda: _pharmacies(db, city))


def _pharmacies(db: Session, city: str) -> Envelope[PharmaciesResponse]:
    pharmacies = db.scalars(select(Pharmacy).order_by(Pharmacy.name, Pharmacy.id))
    areas = db.scalars(select(Area).order_by(Area.name))
    return Envelope(
        data=PharmaciesResponse(
            city=city,
            bbox=SYLHET_BBOX,
            pharmacies=[_pharmacy(p) for p in pharmacies],
            areas=[
                AreaOut(id=a.id, name=a.name, name_bn=a.name_bn, lat=a.lat, lon=a.lon)
                for a in areas
            ],
        )
    )
