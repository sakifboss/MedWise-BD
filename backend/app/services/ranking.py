"""Quality-first ranking of interchangeable brands (formula from CLAUDE.md).

    Q     = 0.30*C + 0.25*E + 0.20*R + 0.15*(1-H) + 0.10*M
    P     = 1 - (price - min_price) / (max_price - min_price)    (P = 1 if all prices equal)
    Final = 100 * (0.8*Q + 0.2*P)

C = certification (who_gmp), E = export footprint, R = compliance,
H = normalised recall history, M = market trust.

Quality factors are min-max normalised across ALL manufacturers, so a manufacturer's
Q is stable no matter which brands are being compared. Price is normalised within the
compared group, as the formula specifies. This module is pure (no database access).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

# Every weight used in ranking lives here.
RANKING_CONFIG: dict[str, dict[str, float]] = {
    "final": {"quality": 0.8, "price": 0.2},
    "quality": {
        "certification": 0.30,
        "export": 0.25,
        "compliance": 0.20,
        "recall": 0.15,
        "market": 0.10,
    },
    # E (export footprint) is built from these normalised raw fields.
    "export": {"export_countries": 0.5, "regulated_market_exports": 0.5},
    # M (market trust) is built from these normalised raw fields.
    "market": {"market_share": 0.5, "years_active": 0.5},
}

RAW_FACTOR_FIELDS = (
    "export_countries",
    "regulated_market_exports",
    "compliance_score",
    "recall_count",
    "market_share",
    "years_active",
)

Bounds = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class ManufacturerFactors:
    id: int
    name: str
    who_gmp: bool
    export_countries: int  # number of countries exported to
    regulated_market_exports: int
    compliance_score: float
    recall_count: int
    market_share: float
    years_active: int


@dataclass(frozen=True)
class BrandCandidate:
    brand_id: int
    name: str
    generic_id: int
    strength: str
    dosage_form: str
    price_per_unit: Decimal
    manufacturer: ManufacturerFactors


@dataclass(frozen=True)
class QualityComponents:
    """Normalised (0-1) inputs to Q."""

    certification: float
    export: float
    compliance: float
    recall_history: float
    market: float


@dataclass(frozen=True)
class RankedBrand:
    rank: int
    candidate: BrandCandidate
    final_score: float
    quality_score: float
    price_score: float
    components: QualityComponents
    reasons: list[str]


# ---------------------------------------------------------------- normalisation


def normalize(value: float, low: float, high: float) -> float:
    """Min-max scale to 0-1 (clamped). If all values are equal: 1 when positive, else 0."""
    if high == low:
        return 1.0 if value > 0 else 0.0
    return min(1.0, max(0.0, (value - low) / (high - low)))


def compute_bounds(manufacturers: Iterable[ManufacturerFactors]) -> Bounds:
    items = list(manufacturers)
    if not items:
        raise ValueError("cannot compute bounds without manufacturers")
    return {
        field: (
            min(float(getattr(m, field)) for m in items),
            max(float(getattr(m, field)) for m in items),
        )
        for field in RAW_FACTOR_FIELDS
    }


def _weighted_mix(m: ManufacturerFactors, bounds: Bounds, weights: dict[str, float]) -> float:
    return sum(w * normalize(float(getattr(m, f)), *bounds[f]) for f, w in weights.items())


# ---------------------------------------------------------------- scores


def quality_components(m: ManufacturerFactors, bounds: Bounds) -> QualityComponents:
    return QualityComponents(
        certification=1.0 if m.who_gmp else 0.0,
        export=_weighted_mix(m, bounds, RANKING_CONFIG["export"]),
        compliance=normalize(m.compliance_score, *bounds["compliance_score"]),
        recall_history=normalize(m.recall_count, *bounds["recall_count"]),
        market=_weighted_mix(m, bounds, RANKING_CONFIG["market"]),
    )


def quality_score(c: QualityComponents) -> float:
    w = RANKING_CONFIG["quality"]
    return (
        w["certification"] * c.certification
        + w["export"] * c.export
        + w["compliance"] * c.compliance
        + w["recall"] * (1 - c.recall_history)
        + w["market"] * c.market
    )


def price_score(price: float, min_price: float, max_price: float) -> float:
    if max_price == min_price:
        return 1.0
    return 1 - (price - min_price) / (max_price - min_price)


def final_score(quality: float, price: float) -> float:
    w = RANKING_CONFIG["final"]
    return 100 * (w["quality"] * quality + w["price"] * price)


# ---------------------------------------------------------------- reasons


def _plural(count: float, word: str, plural: str | None = None) -> str:
    return f"{count:g} {word}" if count == 1 else f"{count:g} {plural or word + 's'}"


def _export_reason(m: ManufacturerFactors) -> str:
    if m.export_countries == 0 and m.regulated_market_exports == 0:
        return "No export record"
    text = f"Exports to {_plural(m.export_countries, 'country', 'countries')}"
    if m.regulated_market_exports:
        text += f", including {_plural(m.regulated_market_exports, 'regulated market')}"
    return text


def _price_reason(price: Decimal, min_price: Decimal, max_price: Decimal) -> str:
    unit = f"Tk {price:.2f}/unit"
    if min_price == max_price:
        return f"Same price as all alternatives ({unit})"
    if price == min_price:
        return f"Lowest price in this group ({unit})"
    extra = (price - min_price) / min_price * 100
    return f"{unit}, {extra:.0f}% more than the cheapest"


def build_reasons(candidate: BrandCandidate, min_price: Decimal, max_price: Decimal) -> list[str]:
    m = candidate.manufacturer
    return [
        "WHO-GMP certified" if m.who_gmp else "Not WHO-GMP certified",
        _export_reason(m),
        f"Compliance score {m.compliance_score:g}/100",
        "No recall on record"
        if m.recall_count == 0
        else f"{_plural(m.recall_count, 'recall')} on record",
        f"{m.market_share:g}% market share, {_plural(m.years_active, 'year')} in operation",
        _price_reason(candidate.price_per_unit, min_price, max_price),
    ]


# ---------------------------------------------------------------- ranking


def _ensure_comparable(candidates: Sequence[BrandCandidate]) -> None:
    groups = {(c.generic_id, c.strength, c.dosage_form) for c in candidates}
    if len(groups) > 1:
        raise ValueError(
            "only brands with the same generic, strength and dosage form can be compared"
        )


def rank_brands(candidates: Sequence[BrandCandidate], bounds: Bounds) -> list[RankedBrand]:
    """Score and order brands, best first. Ties go to the cheaper brand, then by name."""
    if not candidates:
        return []
    _ensure_comparable(candidates)
    min_price = min(c.price_per_unit for c in candidates)
    max_price = max(c.price_per_unit for c in candidates)

    scored = []
    for c in candidates:
        components = quality_components(c.manufacturer, bounds)
        q = quality_score(components)
        p = price_score(float(c.price_per_unit), float(min_price), float(max_price))
        scored.append((final_score(q, p), q, p, components, c))
    scored.sort(key=lambda s: (-s[0], s[4].price_per_unit, s[4].name.casefold()))

    return [
        RankedBrand(
            rank=index,
            candidate=c,
            final_score=final,
            quality_score=q,
            price_score=p,
            components=components,
            reasons=build_reasons(c, min_price, max_price),
        )
        for index, (final, q, p, components, c) in enumerate(scored, start=1)
    ]
