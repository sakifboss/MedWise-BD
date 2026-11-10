from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.db import get_db
from app.models import SEVERITIES, Brand, Generic, Interaction
from app.schemas.common import Envelope, LangQuery
from app.schemas.generic import GenericDetail, GenericListItem, InteractionSummary, Presentation
from app.schemas.seed import TRANSLATED_FIELDS, TRANSLATED_LIST_FIELDS

router = APIRouter(tags=["generics"])


def _presentations(db: Session, generic_id: int) -> list[Presentation]:
    rows = db.execute(
        select(
            Brand.strength,
            Brand.dosage_form,
            func.count(Brand.id),
            func.min(Brand.price_per_unit),
            func.max(Brand.price_per_unit),
        )
        .where(Brand.generic_id == generic_id)
        .group_by(Brand.strength, Brand.dosage_form)
        .order_by(Brand.dosage_form, Brand.strength)
    )
    return [
        Presentation(
            strength=strength,
            dosage_form=form,
            brand_count=count,
            min_price=float(low),
            max_price=float(high),
        )
        for strength, form, count, low, high in rows
    ]


def _interactions(db: Session, generic_id: int, lang: str) -> list[InteractionSummary]:
    other = aliased(Generic)
    other_id = case(
        (Interaction.generic_a_id == generic_id, Interaction.generic_b_id),
        else_=Interaction.generic_a_id,
    )
    rows = db.execute(
        select(
            other.id,
            other.name,
            Interaction.severity,
            Interaction.description,
            Interaction.description_bn,
        )
        .join(other, other.id == other_id)
        .where(or_(Interaction.generic_a_id == generic_id, Interaction.generic_b_id == generic_id))
    )
    items = [
        InteractionSummary(
            generic_id=i,
            generic_name=n,
            severity=s,
            description=(d_bn if lang == "bn" else None) or d,
        )
        for i, n, s, d, d_bn in rows
    ]
    items.sort(key=lambda x: (-SEVERITIES.index(x.severity), x.generic_name.casefold()))
    return items


def _localized(generic: Generic, lang: str) -> tuple[dict[str, Any], list[str]]:
    """Medicine text in the requested language; fields without reviewed Bangla stay English."""
    text: dict[str, Any] = {}
    pending: list[str] = []
    for field in TRANSLATED_FIELDS:
        bangla = getattr(generic, f"{field}_bn") if lang == "bn" else None
        english = getattr(generic, field)
        if english is None and field in TRANSLATED_LIST_FIELDS:
            english = []  # a list field never stored (e.g. added after the row was made)
        text[field] = bangla if bangla is not None else english
        if lang == "bn" and bangla is None and english:
            pending.append(field)  # an empty field has nothing to translate
    return text, pending


@router.get("/generics", response_model=Envelope[list[GenericListItem]])
def list_generics(db: Annotated[Session, Depends(get_db)]) -> Envelope[list[GenericListItem]]:
    """Every generic and its presentations, by name (small: one row per generic)."""
    generics = db.execute(select(Generic.id, Generic.name).order_by(Generic.name)).all()
    return Envelope(
        data=[
            GenericListItem(id=gid, name=name, presentations=_presentations(db, gid))
            for gid, name in generics
        ]
    )


@router.get("/generics/{generic_id}", response_model=Envelope[GenericDetail])
def get_generic(
    generic_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
    lang: LangQuery = "en",
) -> Envelope[GenericDetail]:
    generic = db.get(Generic, generic_id)
    if generic is None:
        raise HTTPException(status_code=404, detail=f"Generic {generic_id} not found")
    text, pending = _localized(generic, lang)
    detail = GenericDetail(
        id=generic.id,
        name=generic.name,
        dosage_forms=generic.dosage_forms,
        source_urls=generic.source_urls,
        translation_pending=pending,
        **text,
        presentations=_presentations(db, generic_id),
        interactions=_interactions(db, generic_id, lang),
    )
    return Envelope(data=detail)
