"""Checking a prescription QR (R4), for the public /rx page.

The page sends only {doctor_id, issued_at, hash, sig}; the medicines stay on the device. Nothing is
stored or logged. The answer says whether MedWise BD's signature matches and, if so, who issued it.
A valid QR proves who issued it, not that the medicines or doses are right; QR codes can be copied.
"""

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.frontend_auth import require_frontend
from app.core.rate_limit import RateLimiter, per_client_limit
from app.models import Doctor
from app.schemas.common import Envelope
from app.schemas.rx import RxDoctorPublic, RxVerifyIn, RxVerifyOut
from app.services import rx_signing

router = APIRouter(tags=["rx"])

verify_limiter = RateLimiter(get_settings().rx_verify_limit_per_minute, 60)
FUTURE_SLACK = 300  # seconds: an issue time later than this is not from us


@router.post(
    "/rx/verify",
    response_model=Envelope[RxVerifyOut],
    dependencies=[Depends(require_frontend), Depends(per_client_limit(verify_limiter))],
)
def verify_rx(body: RxVerifyIn, db: Annotated[Session, Depends(get_db)]) -> Envelope[RxVerifyOut]:
    secret = get_settings().rx_signing_secret
    if body.issued_at > time.time() + FUTURE_SLACK or not rx_signing.verify(
        secret, body.doctor_id, body.issued_at, body.hash, body.sig
    ):
        return Envelope(data=RxVerifyOut(valid=False))
    doctor = db.get(Doctor, body.doctor_id)
    if doctor is None:  # the account was deleted: nobody can stand behind this QR any more
        return Envelope(data=RxVerifyOut(valid=False))
    return Envelope(
        data=RxVerifyOut(
            valid=True,
            doctor=RxDoctorPublic(
                display_name=doctor.display_name,
                display_name_bn=doctor.display_name_bn,
                degrees=doctor.degrees,
                specialty=doctor.specialty,
                bmdc_number=doctor.bmdc_number,
                status=doctor.status,  # type: ignore[arg-type]
                is_demo=doctor.is_demo,
            ),
        )
    )
