"""'Request this medicine': people tell us which medicines to add next.

Stores only the trimmed query, its source and the day. Never an IP address, user agent, cookie
or user id. Only our frontend may call it, and it is rate-limited per client and overall.
Read the log with scripts/top_requests.py; there is no public endpoint that lists requests.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.core.rate_limit import RateLimiter, client_key
from app.models import MedicineRequest
from app.schemas.common import Envelope
from app.schemas.medicine_request import MedicineRequestIn, MedicineRequestSaved

router = APIRouter(tags=["requests"])

HOUR, DAY = 3600, 86400
per_client_limiter = RateLimiter(get_settings().request_limit_per_hour, HOUR)
global_limiter = RateLimiter(get_settings().request_limit_per_day, DAY)


def enforce_rate_limit(request: Request) -> None:
    if not per_client_limiter.allow(client_key(request)):
        raise AppError(429, "rate_limited", "Too many requests from this device. Thank you!")
    if not global_limiter.allow("all"):
        raise AppError(429, "rate_limited", "We have enough requests for today. Thank you!")


@router.post(
    "/requests",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MedicineRequestSaved],
    dependencies=[Depends(require_frontend), Depends(enforce_rate_limit)],
)
def request_medicine(
    body: MedicineRequestIn, db: Annotated[Session, Depends(get_db)]
) -> Envelope[MedicineRequestSaved]:
    db.add(
        MedicineRequest(query=body.query, source=body.source, requested_on=datetime.now(UTC).date())
    )
    db.commit()
    return Envelope(data=MedicineRequestSaved())
