"""Doctor templates and favourite tests (R5).

A template holds medicine lines (brand code with a name snapshot, generic, or a free-text name, with
pattern, unit, food, duration, substitution and the doctor's note), tests and advice. Never patient
fields. Each doctor sees only their own: another doctor's template answers 404. Nothing is shared,
listed for others, ranked or aggregated. At most 100 templates per doctor, 12 lines each.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.doctor import CurrentDoctor, Db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.models import MAX_TEMPLATES, Brand, Doctor, DoctorTemplate
from app.schemas.common import Envelope
from app.schemas.doctor import Done
from app.schemas.doctor_templates import (
    FavouriteTests,
    TemplateIn,
    TemplateLineOut,
    TemplateOut,
    TemplateRename,
    TemplateSummary,
)
from app.services.doctor_auth import require_same_site, utcnow

router = APIRouter(prefix="/doctor", tags=["doctor"], dependencies=[Depends(require_frontend)])
SAME_SITE = [Depends(require_same_site)]
TemplateId = Annotated[int, Path(ge=1)]


def _own(db: Session, doctor: Doctor, template_id: int) -> DoctorTemplate:
    template = db.scalar(
        select(DoctorTemplate).where(
            DoctorTemplate.id == template_id, DoctorTemplate.doctor_id == doctor.id
        )
    )
    if template is None:  # someone else's template looks exactly like a missing one
        raise AppError(404, "not_found", "Template not found.")
    return template


def _name_taken(db: Session, doctor: Doctor, name: str, except_id: int | None = None) -> bool:
    query = select(DoctorTemplate.id).where(
        DoctorTemplate.doctor_id == doctor.id, func.lower(DoctorTemplate.name) == name.lower()
    )
    if except_id is not None:
        query = query.where(DoctorTemplate.id != except_id)
    return db.scalar(query) is not None


def _out(db: Session, template: DoctorTemplate) -> TemplateOut:
    """The template as saved; a brand that has left the catalog becomes a free-text line."""
    codes = {line.get("code") for line in template.lines if line.get("kind") == "brand"}
    known = set(db.scalars(select(Brand.code).where(Brand.code.in_(codes)))) if codes else set()
    lines = []
    for raw in template.lines:
        line = TemplateLineOut.model_validate(raw)
        if line.kind == "brand" and line.code not in known:
            line = line.model_copy(update={"kind": "free", "code": None, "gone": True})
        lines.append(line)
    return TemplateOut(
        id=template.id,
        name=template.name,
        lines=lines,
        tests=template.tests,
        advice=template.advice,
        updated_at=template.updated_at,
    )


def _summary(template: DoctorTemplate) -> TemplateSummary:
    return TemplateSummary(
        id=template.id,
        name=template.name,
        line_count=len(template.lines),
        updated_at=template.updated_at,
    )


@router.get("/templates", response_model=Envelope[list[TemplateSummary]])
def list_templates(db: Db, doctor: CurrentDoctor) -> Envelope[list[TemplateSummary]]:
    rows = db.scalars(
        select(DoctorTemplate)
        .where(DoctorTemplate.doctor_id == doctor.id)
        .order_by(func.lower(DoctorTemplate.name))
    )
    return Envelope(data=[_summary(t) for t in rows])


@router.get("/templates/{template_id}", response_model=Envelope[TemplateOut])
def get_template(template_id: TemplateId, db: Db, doctor: CurrentDoctor) -> Envelope[TemplateOut]:
    return Envelope(data=_out(db, _own(db, doctor, template_id)))


@router.post(
    "/templates", status_code=201, response_model=Envelope[TemplateOut], dependencies=SAME_SITE
)
def create_template(body: TemplateIn, db: Db, doctor: CurrentDoctor) -> Envelope[TemplateOut]:
    count = db.scalar(
        select(func.count())
        .select_from(DoctorTemplate)
        .where(DoctorTemplate.doctor_id == doctor.id)
    )
    if (count or 0) >= MAX_TEMPLATES:
        raise AppError(409, "template_limit", f"At most {MAX_TEMPLATES} templates.")
    if _name_taken(db, doctor, body.name):
        raise AppError(409, "template_name_taken", "A template with this name exists.")
    now = utcnow()
    template = DoctorTemplate(
        doctor_id=doctor.id,
        name=body.name,
        lines=[line.model_dump() for line in body.lines],
        tests=body.tests,
        advice=body.advice,
        created_at=now,
        updated_at=now,
    )
    db.add(template)
    db.commit()
    return Envelope(data=_out(db, template))


@router.post(
    "/templates/{template_id}", response_model=Envelope[TemplateOut], dependencies=SAME_SITE
)
def update_template(
    template_id: TemplateId, body: TemplateIn, db: Db, doctor: CurrentDoctor
) -> Envelope[TemplateOut]:
    template = _own(db, doctor, template_id)
    if _name_taken(db, doctor, body.name, except_id=template.id):
        raise AppError(409, "template_name_taken", "A template with this name exists.")
    template.name = body.name
    template.lines = [line.model_dump() for line in body.lines]
    template.tests = body.tests
    template.advice = body.advice
    template.updated_at = utcnow()
    db.commit()
    return Envelope(data=_out(db, template))


@router.post(
    "/templates/{template_id}/rename",
    response_model=Envelope[TemplateSummary],
    dependencies=SAME_SITE,
)
def rename_template(
    template_id: TemplateId, body: TemplateRename, db: Db, doctor: CurrentDoctor
) -> Envelope[TemplateSummary]:
    name = body.name
    template = _own(db, doctor, template_id)
    if _name_taken(db, doctor, name, except_id=template.id):
        raise AppError(409, "template_name_taken", "A template with this name exists.")
    template.name = name
    template.updated_at = utcnow()
    db.commit()
    return Envelope(data=_summary(template))


@router.post(
    "/templates/{template_id}/delete", response_model=Envelope[Done], dependencies=SAME_SITE
)
def delete_template(template_id: TemplateId, db: Db, doctor: CurrentDoctor) -> Envelope[Done]:
    db.delete(_own(db, doctor, template_id))
    db.commit()
    return Envelope(data=Done())


@router.get("/favourite-tests", response_model=Envelope[FavouriteTests])
def get_favourite_tests(doctor: CurrentDoctor) -> Envelope[FavouriteTests]:
    return Envelope(data=FavouriteTests(tests=doctor.favourite_tests or []))


@router.post("/favourite-tests", response_model=Envelope[FavouriteTests], dependencies=SAME_SITE)
def save_favourite_tests(
    body: FavouriteTests, db: Db, doctor: CurrentDoctor
) -> Envelope[FavouriteTests]:
    doctor.favourite_tests = body.tests
    db.commit()
    return Envelope(data=FavouriteTests(tests=body.tests))
