"""Checks a set of medicines for recorded interactions and duplicate generics.

Everything comes from the interactions table; nothing is inferred. "No interactions found"
only means none are recorded in our data. Generics the catalog lists only in local forms (eye
drops, creams, ...) have no DDInter pairs (app/services/local_forms.py); they are reported as
"not shown", with their forms, so pages can say why.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import SEVERITIES, Brand, DosageForm, Generic, Interaction
from app.services.local_forms import local_only_forms

MAX_MEDICINES = 20


@dataclass
class CheckedGeneric:
    id: int
    name: str
    brands: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FoundInteraction:
    generic_a: CheckedGeneric
    generic_b: CheckedGeneric
    severity: str
    description: str
    description_bn: str | None = None

    def text(self, lang: str) -> str:
        """Description in the requested language, falling back to English."""
        return (self.description_bn if lang == "bn" else None) or self.description


@dataclass(frozen=True)
class NotShown:
    """A generic whose interactions are not shown: the catalog lists it only in local forms."""

    generic: CheckedGeneric
    forms: list[str]


@dataclass
class InteractionReport:
    medicines: list[CheckedGeneric]
    interactions: list[FoundInteraction]
    duplicates: list[CheckedGeneric]  # one generic chosen via 2+ different brands
    not_shown: list[NotShown] = field(default_factory=list)

    @property
    def pairs_checked(self) -> int:
        """Pairs among the medicines whose interactions we have (local-only ones excluded)."""
        n = len(self.medicines) - len(self.not_shown)
        return n * (n - 1) // 2 if n > 1 else 0


def local_only_forms_by_id(db: Session, generic_ids: Iterable[int]) -> dict[int, list[str]]:
    """Generic id -> forms, for the given generics whose every catalog brand is a local form."""
    ids = set(generic_ids)
    if not ids:
        return {}
    routes = {name: route for name, route in db.execute(select(DosageForm.name, DosageForm.route))}
    rows = db.execute(
        select(Brand.generic_id, Brand.dosage_form).where(Brand.generic_id.in_(ids)).distinct()
    )
    return local_only_forms(((gid, form) for gid, form in rows), routes)


def _missing(kind: str, requested: set[int], found: set[int]) -> None:
    missing = sorted(requested - found)
    if missing:
        ids = ", ".join(str(i) for i in missing)
        raise AppError(404, "not_found", f"Unknown {kind} id(s): {ids}")


def resolve_generics(
    db: Session, generic_ids: list[int], brand_ids: list[int]
) -> list[CheckedGeneric]:
    """Map the requested brands and generics to distinct generics, keeping brand names."""
    if len(set(generic_ids)) + len(set(brand_ids)) > MAX_MEDICINES:
        raise AppError(
            400, "too_many_medicines", f"Check at most {MAX_MEDICINES} medicines at once."
        )

    checked: dict[int, CheckedGeneric] = {}
    if brand_ids:
        rows = db.execute(
            select(Brand.id, Brand.name, Generic.id, Generic.name)
            .join(Generic, Brand.generic_id == Generic.id)
            .where(Brand.id.in_(set(brand_ids)))
        ).all()
        _missing("brand", set(brand_ids), {r[0] for r in rows})
        for _, brand_name, generic_id, generic_name in rows:
            entry = checked.setdefault(generic_id, CheckedGeneric(generic_id, generic_name))
            if brand_name not in entry.brands:
                entry.brands.append(brand_name)

    if generic_ids:
        rows = db.execute(
            select(Generic.id, Generic.name).where(Generic.id.in_(set(generic_ids)))
        ).all()
        _missing("generic", set(generic_ids), {r[0] for r in rows})
        for generic_id, generic_name in rows:
            checked.setdefault(generic_id, CheckedGeneric(generic_id, generic_name))

    return sorted(checked.values(), key=lambda g: g.name.casefold())


def find_interactions(db: Session, medicines: list[CheckedGeneric]) -> list[FoundInteraction]:
    by_id = {g.id: g for g in medicines}
    if len(by_id) < 2:
        return []
    rows = db.execute(
        select(
            Interaction.generic_a_id,
            Interaction.generic_b_id,
            Interaction.severity,
            Interaction.description,
            Interaction.description_bn,
        ).where(Interaction.generic_a_id.in_(by_id), Interaction.generic_b_id.in_(by_id))
    ).all()
    found = [
        FoundInteraction(by_id[x], by_id[y], sev, desc, desc_bn)
        for x, y, sev, desc, desc_bn in rows
    ]
    found.sort(
        key=lambda f: (
            -SEVERITIES.index(f.severity),
            f.generic_a.name.casefold(),
            f.generic_b.name.casefold(),
        )
    )
    return found


def check_interactions(
    db: Session, generic_ids: list[int], brand_ids: list[int]
) -> InteractionReport:
    medicines = resolve_generics(db, generic_ids, brand_ids)
    local = local_only_forms_by_id(db, (g.id for g in medicines))
    return InteractionReport(
        medicines=medicines,
        interactions=find_interactions(db, [g for g in medicines if g.id not in local]),
        duplicates=[g for g in medicines if len(g.brands) > 1],
        not_shown=[NotShown(g, local[g.id]) for g in medicines if g.id in local],
    )
