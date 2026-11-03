"""Quality-first ranking of interchangeable brands (formula from CLAUDE.md).

    Q     = 0.30*C + 0.25*E + 0.20*R + 0.15*(1-H) + 0.10*M
    P     = 1 - (price - min_price) / (max_price - min_price)    (P = 1 if all prices equal)
    Final = 100 * (0.8*Q + 0.2*P)

C = certification: share of the four stringent regulators (US FDA, UK MHRA, EU GMP,
    TGA Australia) that approved at least one of the manufacturer's plants
E = export footprint, R = compliance (absolute 0-100 score / 100),
H = normalised recall history, M = market trust.

Export, recall and market factors are min-max normalised across ALL manufacturers, so
a manufacturer's Q is stable no matter which brands are being compared. Price is
normalised within the compared group, as the formula specifies. An unknown market
share counts as 0. This module is pure (no database access).
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

STRINGENT_REGULATORS: tuple[str, ...] = ("US FDA", "UK MHRA", "EU GMP", "TGA Australia")

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
    stringent_approvals: tuple[str, ...]
    export_countries: int  # number of countries exported to
    regulated_market_exports: int
    compliance_score: float
    recall_count: int
    market_share: float | None  # None = unknown, scored as 0
    years_active: int
    recall_data_available: bool = True
    source_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrandCandidate:
    brand_id: int
    name: str
    generic_id: int
    strength: str
    dosage_form: str
    price_per_unit: Decimal
    manufacturer: ManufacturerFactors
    price_source_url: str | None = None


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


def _raw(m: ManufacturerFactors, field: str) -> float:
    value = getattr(m, field)
    return 0.0 if value is None else float(value)


def compute_bounds(manufacturers: Iterable[ManufacturerFactors]) -> Bounds:
    items = list(manufacturers)
    if not items:
        raise ValueError("cannot compute bounds without manufacturers")
    return {
        field: (min(_raw(m, field) for m in items), max(_raw(m, field) for m in items))
        for field in RAW_FACTOR_FIELDS
    }


def _weighted_mix(m: ManufacturerFactors, bounds: Bounds, weights: dict[str, float]) -> float:
    return sum(w * normalize(_raw(m, f), *bounds[f]) for f, w in weights.items())


def certification_score(m: ManufacturerFactors) -> float:
    approved = {r for r in m.stringent_approvals if r in STRINGENT_REGULATORS}
    return len(approved) / len(STRINGENT_REGULATORS)


# ---------------------------------------------------------------- scores


def quality_components(m: ManufacturerFactors, bounds: Bounds) -> QualityComponents:
    return QualityComponents(
        certification=certification_score(m),
        export=_weighted_mix(m, bounds, RANKING_CONFIG["export"]),
        compliance=min(1.0, max(0.0, m.compliance_score / 100)),
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


def _certification_reason(m: ManufacturerFactors) -> str:
    approved = [r for r in STRINGENT_REGULATORS if r in m.stringent_approvals]
    if not approved:
        return "No US FDA, UK MHRA, EU GMP or TGA plant approval found"
    return f"Has plant(s) approved by {', '.join(approved)}"


def _recall_reason(m: ManufacturerFactors) -> str:
    if not m.recall_data_available:
        return "Recall history not available"
    if m.recall_count == 0:
        return "No recall on record"
    return f"{_plural(m.recall_count, 'recall')} on record"


def _market_reason(m: ManufacturerFactors) -> str:
    years = _plural(m.years_active, "year")
    if m.market_share is None:
        return f"{years} in operation (market share not available)"
    return f"{m.market_share:g}% market share, {years} in operation"


def _reasons_en(candidate: BrandCandidate, min_price: Decimal, max_price: Decimal) -> list[str]:
    m = candidate.manufacturer
    return [
        _certification_reason(m),
        _export_reason(m),
        f"Compliance score {m.compliance_score:g}/100",
        _recall_reason(m),
        _market_reason(m),
        _price_reason(candidate.price_per_unit, min_price, max_price),
    ]


# Bangla: the same facts as the English reasons, worded for Bangla readers.
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _bn(value: object) -> str:
    return str(value).translate(_BN_DIGITS)


def _num_bn(value: float) -> str:
    return _bn(f"{value:g}")


def _reasons_bn(candidate: BrandCandidate, min_price: Decimal, max_price: Decimal) -> list[str]:
    m = candidate.manufacturer
    approved = [r for r in STRINGENT_REGULATORS if r in m.stringent_approvals]
    certification = (
        f"{', '.join(approved)}-এর অনুমোদিত প্ল্যান্ট আছে"
        if approved
        else "US FDA, UK MHRA, EU GMP বা TGA-র কোনো প্ল্যান্ট অনুমোদন পাওয়া যায়নি"
    )

    if m.export_countries == 0 and m.regulated_market_exports == 0:
        export = "রপ্তানির কোনো তথ্য নেই"
    else:
        export = f"{_num_bn(m.export_countries)}টি দেশে রপ্তানি করে"
        if m.regulated_market_exports:
            export += f", এর মধ্যে {_num_bn(m.regulated_market_exports)}টি নিয়ন্ত্রিত বাজার"

    if not m.recall_data_available:
        recall = "রিকলের ইতিহাস পাওয়া যায়নি"
    elif m.recall_count == 0:
        recall = "কোনো রিকলের রেকর্ড নেই"
    else:
        recall = f"{_num_bn(m.recall_count)}টি রিকলের রেকর্ড আছে"

    years = f"{_num_bn(m.years_active)} বছর ধরে চালু"
    market = (
        f"{years} (বাজারের অংশ জানা নেই)"
        if m.market_share is None
        else f"বাজারের {_num_bn(m.market_share)}% অংশ, {years}"
    )

    price = candidate.price_per_unit
    unit = f"৳{_bn(f'{price:.2f}')}/ইউনিট"
    if min_price == max_price:
        price_text = f"সব বিকল্পের দাম একই ({unit})"
    elif price == min_price:
        price_text = f"এই গ্রুপে সবচেয়ে কম দাম ({unit})"
    else:
        extra = (price - min_price) / min_price * 100
        price_text = f"{unit}, সবচেয়ে সস্তাটির চেয়ে {_bn(f'{extra:.0f}')}% বেশি"

    return [
        certification,
        export,
        f"কমপ্লায়েন্স স্কোর {_num_bn(m.compliance_score)}/১০০",
        recall,
        market,
        price_text,
    ]


def build_reasons(
    candidate: BrandCandidate, min_price: Decimal, max_price: Decimal, lang: str = "en"
) -> list[str]:
    builder = _reasons_bn if lang == "bn" else _reasons_en
    return builder(candidate, min_price, max_price)


# ---------------------------------------------------------------- ranking


def _ensure_comparable(candidates: Sequence[BrandCandidate]) -> None:
    groups = {(c.generic_id, c.strength, c.dosage_form) for c in candidates}
    if len(groups) > 1:
        raise ValueError(
            "only brands with the same generic, strength and dosage form can be compared"
        )


def rank_brands(
    candidates: Sequence[BrandCandidate], bounds: Bounds, lang: str = "en"
) -> list[RankedBrand]:
    """Score and order brands, best first. Ties go to the cheaper brand, then by name.

    `lang` ("en" or "bn") only changes the wording of `reasons`, never the scores.
    """
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
            reasons=build_reasons(c, min_price, max_price, lang),
        )
        for index, (final, q, p, components, c) in enumerate(scored, start=1)
    ]
