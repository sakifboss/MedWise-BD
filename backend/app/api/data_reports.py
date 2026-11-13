"""'Report a problem' with a brand's data (price, still sold, manufacturer).

Stores only the brand (with its details, since ids change on import), a fixed reason and the day.
Never free text, an IP address, user agent, cookie or user id. Only our frontend may call it, and
it is rate-limited per client and overall. The team reads reports with scripts/top_reports.py and
fixes the seed files; there is no public endpoint that lists reports.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.core.rate_limit import RateLimiter, client_key
from app.models import Brand, DataReport, Manufacturer
from app.schemas.common import Envelope
from app.schemas.data_report import DataReportIn, DataReportSaved

router = APIRouter(tags=["reports"])

HOUR, DAY = 3600, 86400
per_client_limiter = RateLimiter(get_settings().report_limit_per_hour, HOUR)
global_limiter = RateLimiter(get_settings().report_limit_per_day, DAY)


def enforce_rate_limit(request: Request) -> None:
    if not per_client_limiter.allow(client_key(request)):
        raise AppError(429, "rate_limited", "Too many reports from this device. Thank you!")
    if not global_limiter.allow("all"):
        raise AppError(429, "rate_limited", "We have enough reports for today. Thank you!")


@router.post(
    "/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[DataReportSaved],
    dependencies=[Depends(require_frontend), Depends(enforce_rate_limit)],
)
def report_problem(
    body: DataReportIn, db: Annotated[Session, Depends(get_db)]
) -> Envelope[DataReportSaved]:
    row = db.execute(
        select(Brand.name, Manufacturer.name, Brand.strength, Brand.dosage_form, Brand.code)
        .join(Manufacturer, Brand.manufacturer_id == Manufacturer.id)
        .where(Brand.id == body.brand_id)
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Brand not found")
    name, manufacturer, strength, form, code = row
    db.add(
        DataReport(
            brand_id=body.brand_id,
            brand_code=code,
            brand_name=name,
            manufacturer=manufacturer,
            strength=strength,
            dosage_form=form,
            reason=body.reason,
            reported_on=datetime.now(UTC).date(),
        )
    )
    db.commit()
    return Envelope(data=DataReportSaved())
