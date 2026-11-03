"""Manufacturer quality, explained factor by factor with the same maths as services/ranking.py."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Manufacturer
from app.services.alternatives import to_factors
from app.services.ranking import (
    RANKING_CONFIG,
    QualityComponents,
    compute_bounds,
    quality_components,
    quality_score,
)


@dataclass(frozen=True)
class RatedManufacturer:
    manufacturer: Manufacturer
    components: QualityComponents
    quality: float  # 0-1
    rank: int


def rate_all(db: Session) -> list[RatedManufacturer]:
    """Every manufacturer with its quality score, best first (ties by name)."""
    manufacturers = list(db.scalars(select(Manufacturer)))
    if not manufacturers:
        return []
    factors = {m.id: to_factors(m) for m in manufacturers}
    bounds = compute_bounds(factors.values())
    scored = []
    for m in manufacturers:
        components = quality_components(factors[m.id], bounds)
        scored.append((m, components, quality_score(components)))
    scored.sort(key=lambda s: (-s[2], s[0].name.casefold()))
    return [
        RatedManufacturer(manufacturer=m, components=c, quality=q, rank=i)
        for i, (m, c, q) in enumerate(scored, start=1)
    ]


def factor_breakdown(c: QualityComponents) -> list[tuple[str, float, float]]:
    """(key, weight, score) per factor; recall history is inverted so higher is always better."""
    w = RANKING_CONFIG["quality"]
    return [
        ("certification", w["certification"], c.certification),
        ("export", w["export"], c.export),
        ("compliance", w["compliance"], c.compliance),
        ("recall_history", w["recall"], 1 - c.recall_history),
        ("market", w["market"], c.market),
    ]


def unknown_facts(m: Manufacturer) -> list[str]:
    unknown = []
    if not m.recall_data_available:
        unknown.append("recall_history")
    if m.market_share is None:
        unknown.append("market_share")
    if m.export_country_count is None and not m.export_countries:
        unknown.append("export_country_count")
    return unknown
