"""Symptom guide: emergency signs (no AI) and which kind of doctor to start with (Gemini).

The guide never diagnoses and never names a disease or a medicine (see services/symptom_guide.py).
What the person writes is sent to Gemini to be processed and is never stored or logged here.
"""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.core.rate_limit import RateLimiter, client_key, per_client_limit
from app.models import Brand, Generic, RedFlag, Specialty
from app.schemas.common import Envelope
from app.schemas.symptom_guide import (
    RedFlagOut,
    SpecialtyOut,
    SymptomGuideIn,
    SymptomGuideOut,
    SymptomGuideSetup,
)
from app.services.gemini import GeminiClient
from app.services.symptom_guide import load_words, run_guide

router = APIRouter(tags=["symptom guide"])

HOUR, DAY = 3600, 86400
per_client_limiter = RateLimiter(get_settings().symptom_limit_per_hour, HOUR)
global_limiter = RateLimiter(get_settings().symptom_limit_per_day, DAY)
setup_limiter = RateLimiter(get_settings().search_limit_per_minute, 60)

Generate = Callable[[dict], str]


def get_generator() -> Generate | None:
    """The Gemini call, or None when no key is set (the guide then uses the fallback)."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    return GeminiClient(settings).generate


def enforce_rate_limit(request: Request) -> None:
    # Per-client first, so a client that is already blocked doesn't use up everyone's quota.
    if not per_client_limiter.allow(client_key(request)):
        raise AppError(429, "rate_limited", "Too many questions from this device. Try in an hour.")
    if not global_limiter.allow("all"):
        raise AppError(429, "guide_busy", "The symptom guide has reached today's limit.")


def _specialty_out(s: Specialty, lang: str) -> SpecialtyOut:
    bn = lang == "bn"
    return SpecialtyOut(
        id=s.key,
        name=(s.name_bn if bn and s.name_bn else s.name),
        covers=(s.covers_bn if bn and s.covers_bn else s.covers),
    )


@router.get(
    "/symptom-guide/setup",
    response_model=Envelope[SymptomGuideSetup],
    dependencies=[Depends(per_client_limit(setup_limiter))],
)
def setup(
    db: Annotated[Session, Depends(get_db)],
    lang: Annotated[Literal["en", "bn"], Query()] = "en",
) -> Envelope[SymptomGuideSetup]:
    """The emergency checklist (NHS wording, in order) and the specialties."""
    bn = lang == "bn"
    flags = [
        RedFlagOut(
            id=f.key,
            group=f.group,
            text=(f.text_bn if bn and f.text_bn else f.text),
            source_url=f.source_url,
        )
        for f in db.scalars(select(RedFlag).order_by(RedFlag.id))
    ]
    specialties = [
        _specialty_out(s, lang) for s in db.scalars(select(Specialty).order_by(Specialty.id))
    ]
    return Envelope(data=SymptomGuideSetup(red_flags=flags, specialties=specialties))


def _catalog_names(db: Session) -> list[str]:
    brands = db.scalars(select(Brand.name).distinct())
    generics = db.scalars(select(Generic.name))
    return sorted({*brands, *generics})


@router.post(
    "/symptom-guide",
    response_model=Envelope[SymptomGuideOut],
    # The frontend check runs first, so direct calls never count against the rate limits.
    dependencies=[Depends(require_frontend), Depends(enforce_rate_limit)],
)
def symptom_guide(
    answers: SymptomGuideIn,
    db: Annotated[Session, Depends(get_db)],
    generate: Annotated[Generate | None, Depends(get_generator)],
) -> Envelope[SymptomGuideOut]:
    """Which kind of doctor to start with, and a short note. Not a diagnosis."""
    specialties = {s.key: s for s in db.scalars(select(Specialty))}
    result = run_guide(
        answers,
        {key: s.covers for key, s in specialties.items()},
        _catalog_names(db),
        load_words(get_settings().symptom_words_path),
        generate,
    )
    specialty = specialties.get(result.specialty or "")
    return Envelope(
        data=SymptomGuideOut(
            emergency=result.emergency,
            specialty=_specialty_out(specialty, answers.lang) if specialty else None,
            note=result.note,
            note_written_by=result.note_written_by,
            rule=result.rule,
        )
    )
