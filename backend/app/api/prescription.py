from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter, client_key
from app.schemas.common import Envelope
from app.schemas.prescription import MatchOptionOut, PrescriptionItem, PrescriptionResponse
from app.services.ocr import Extractor, GeminiExtractor
from app.services.prescription import PrescriptionMatch, match_prescription

router = APIRouter(tags=["prescription"])

HOUR, DAY = 3600, 86400
per_client_limiter = RateLimiter(get_settings().prescription_limit_per_hour, HOUR)
global_limiter = RateLimiter(get_settings().prescription_limit_per_day, DAY)


def get_extractor() -> Extractor:
    return GeminiExtractor(get_settings())


def enforce_rate_limit(request: Request) -> None:
    # Per-client first, so a client that is already blocked doesn't use up everyone's quota.
    if not per_client_limiter.allow(client_key(request)):
        raise AppError(
            429, "rate_limited", "Too many prescriptions from this device. Try again in an hour."
        )
    if not global_limiter.allow("all"):
        raise AppError(
            429, "ocr_busy", "Prescription reading has reached today's limit. Try tomorrow."
        )


def detect_image_type(data: bytes) -> str | None:
    """Identify the image from its bytes; the client-declared content type is not trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1"):
        return "image/heic"
    return None


def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    max_bytes = int(get_settings().max_upload_mb * 1024 * 1024)
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise AppError(
            413, "file_too_large", f"Image must be under {get_settings().max_upload_mb:g} MB."
        )
    mime_type = detect_image_type(data)
    if mime_type is None:
        raise AppError(400, "unsupported_file", "Upload a photo in JPEG, PNG, WebP or HEIC format.")
    return data, mime_type


def _to_item(match: PrescriptionMatch) -> PrescriptionItem:
    return PrescriptionItem(
        extracted_name=match.extracted.name,
        extracted_strength=match.extracted.strength,
        options=[
            MatchOptionOut(**{**o.__dict__, "score": round(o.score, 1)}) for o in match.options
        ],
        suggested_index=match.suggested_index,
    )


@router.post(
    "/prescription",
    response_model=Envelope[PrescriptionResponse],
    dependencies=[Depends(enforce_rate_limit)],
)
def read_prescription(
    image: Annotated[UploadFile, File(description="Photo of the prescription")],
    db: Annotated[Session, Depends(get_db)],
    extractor: Annotated[Extractor, Depends(get_extractor)],
) -> Envelope[PrescriptionResponse]:
    """Extract medicine names + strengths from a photo and propose database matches.

    The image is processed in memory and never stored. Results must be confirmed by the user.
    """
    data, mime_type = _read_image(image)
    try:
        medicines = extractor(data, mime_type)
    finally:
        del data
    items = [_to_item(m) for m in match_prescription(db, medicines)]
    return Envelope(data=PrescriptionResponse(items=items))
