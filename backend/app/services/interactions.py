"""Checks a set of medicines for recorded interactions and duplicate generics.

Everything comes from the interactions table; nothing is inferred. "No interactions found"
only means none are recorded in our data.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import SEVERITIES, Brand, Generic, Interaction

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


@dataclass
class InteractionReport:
    medicines: list[CheckedGeneric]
    interactions: list[FoundInteraction]
    duplicates: list[CheckedGeneric]  # one generic chosen via 2+ different brands

    @property
    def pairs_checked(self) -> int:
        n = len(self.medicines)
        return n * (n - 1) // 2


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
        ).where(Interaction.generic_a_id.in_(by_id), Interaction.generic_b_id.in_(by_id))
    ).all()
    found = [FoundInteraction(by_id[x], by_id[y], sev, desc) for x, y, sev, desc in rows]
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
    return InteractionReport(
        medicines=medicines,
        interactions=find_interactions(db, medicines),
        duplicates=[g for g in medicines if len(g.brands) > 1],
    )
