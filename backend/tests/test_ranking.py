"""Unit tests for app/services/ranking.py.

Hand-worked example (bounds come from manufacturers A, B, C):
    A: best on every factor           -> C=1, E=1,   R=1,   H=0,   M=1   -> Q = 1.00
    B: worst on every factor          -> C=0, E=0,   R=0,   H=1,   M=0   -> Q = 0.00
    C: WHO-GMP, midway on the rest    -> C=1, E=0.5, R=0.5, H=0.5, M=0.5 -> Q = 0.65
    Prices A=10, B=5, C=7.5           -> P_A=0, P_B=1, P_C=0.5
    Final = 100*(0.8Q + 0.2P)         -> A=80, C=62, B=20
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.services.ranking import (
    RANKING_CONFIG,
    BrandCandidate,
    ManufacturerFactors,
    compute_bounds,
    final_score,
    normalize,
    price_score,
    quality_components,
    quality_score,
    rank_brands,
)

A = ManufacturerFactors(1, "Alpha", True, 10, 4, 90, 0, 20, 50)
B = ManufacturerFactors(2, "Beta", False, 0, 0, 70, 4, 0, 10)
C = ManufacturerFactors(3, "Gamma", True, 5, 2, 80, 2, 10, 30)
BOUNDS = compute_bounds([A, B, C])


def brand(
    brand_id: int, manufacturer: ManufacturerFactors, price: str, **kw: object
) -> BrandCandidate:
    fields: dict = {
        "brand_id": brand_id,
        "name": f"Brand{brand_id}",
        "generic_id": 1,
        "strength": "500 mg",
        "dosage_form": "tablet",
        "price_per_unit": Decimal(price),
        "manufacturer": manufacturer,
    }
    fields.update(kw)
    return BrandCandidate(**fields)


GROUP = [brand(1, A, "10.00"), brand(2, B, "5.00"), brand(3, C, "7.50")]


# ---------------------------------------------------------------- config


@pytest.mark.parametrize("section", ["final", "quality", "export", "market"])
def test_weights_in_each_section_sum_to_one(section: str) -> None:
    assert sum(RANKING_CONFIG[section].values()) == pytest.approx(1.0)


def test_formula_weights_match_claude_md() -> None:
    assert RANKING_CONFIG["final"] == {"quality": 0.8, "price": 0.2}
    assert RANKING_CONFIG["quality"] == {
        "certification": 0.30,
        "export": 0.25,
        "compliance": 0.20,
        "recall": 0.15,
        "market": 0.10,
    }


# ---------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("value", "low", "high", "expected"),
    [
        (5, 0, 10, 0.5),
        (0, 0, 10, 0.0),
        (10, 0, 10, 1.0),
        (15, 0, 10, 1.0),  # clamped
        (-1, 0, 10, 0.0),  # clamped
        (7, 7, 7, 1.0),  # all equal and positive
        (0, 0, 0, 0.0),  # all equal and zero (e.g. nobody has recalls)
    ],
)
def test_normalize(value: float, low: float, high: float, expected: float) -> None:
    assert normalize(value, low, high) == pytest.approx(expected)


def test_compute_bounds_requires_manufacturers() -> None:
    with pytest.raises(ValueError):
        compute_bounds([])


# ---------------------------------------------------------------- component scores


def test_quality_components_hand_example() -> None:
    c = quality_components(C, BOUNDS)
    assert c.certification == 1.0
    assert c.export == pytest.approx(0.5)
    assert c.compliance == pytest.approx(0.5)
    assert c.recall_history == pytest.approx(0.5)
    assert c.market == pytest.approx(0.5)


@pytest.mark.parametrize(("m", "expected"), [(A, 1.0), (B, 0.0), (C, 0.65)])
def test_quality_score_hand_example(m: ManufacturerFactors, expected: float) -> None:
    assert quality_score(quality_components(m, BOUNDS)) == pytest.approx(expected)


def test_recall_history_lowers_quality() -> None:
    recalled = replace(A, recall_count=4)
    assert quality_score(quality_components(recalled, BOUNDS)) == pytest.approx(1.0 - 0.15)


@pytest.mark.parametrize(("price", "expected"), [(5.0, 1.0), (10.0, 0.0), (7.5, 0.5)])
def test_price_score(price: float, expected: float) -> None:
    assert price_score(price, 5.0, 10.0) == pytest.approx(expected)


def test_price_score_is_one_when_all_prices_equal() -> None:
    assert price_score(8.0, 8.0, 8.0) == 1.0


def test_final_score() -> None:
    assert final_score(0.65, 0.5) == pytest.approx(62.0)
    assert final_score(1.0, 1.0) == pytest.approx(100.0)
    assert final_score(0.0, 0.0) == 0.0


# ---------------------------------------------------------------- rank_brands


def test_rank_brands_hand_example() -> None:
    ranked = rank_brands(GROUP, BOUNDS)
    assert [r.candidate.brand_id for r in ranked] == [1, 3, 2]
    assert [r.rank for r in ranked] == [1, 2, 3]
    assert [r.final_score for r in ranked] == pytest.approx([80.0, 62.0, 20.0])
    assert [r.price_score for r in ranked] == pytest.approx([0.0, 0.5, 1.0])


def test_quality_outweighs_price() -> None:
    # Best manufacturer at 10x the price still beats the worst one at the lowest price.
    ranked = rank_brands([brand(1, A, "50.00"), brand(2, B, "5.00")], BOUNDS)
    assert ranked[0].candidate.brand_id == 1


def test_quality_does_not_depend_on_group() -> None:
    alone = rank_brands([brand(3, C, "7.50")], BOUNDS)[0]
    assert alone.quality_score == pytest.approx(0.65)
    assert alone.price_score == 1.0  # only brand -> all prices equal
    assert alone.final_score == pytest.approx(100 * (0.8 * 0.65 + 0.2))


def test_ties_go_to_cheaper_then_name() -> None:
    same_score = [
        brand(1, A, "10.00", name="Zeta"),
        brand(2, A, "10.00", name="alpha"),
    ]
    ranked = rank_brands(same_score, BOUNDS)
    assert [r.candidate.name for r in ranked] == ["alpha", "Zeta"]


def test_empty_group() -> None:
    assert rank_brands([], BOUNDS) == []


@pytest.mark.parametrize(
    "odd_one",
    [
        {"generic_id": 2},
        {"strength": "250 mg"},
        {"dosage_form": "capsule"},
    ],
)
def test_rejects_brands_that_are_not_comparable(odd_one: dict) -> None:
    with pytest.raises(ValueError, match="same generic, strength and dosage form"):
        rank_brands([brand(1, A, "1.00"), brand(2, B, "1.00", **odd_one)], BOUNDS)


# ---------------------------------------------------------------- reasons


def test_reasons_for_strong_manufacturer() -> None:
    reasons = rank_brands(GROUP, BOUNDS)[0].reasons
    assert "WHO-GMP certified" in reasons
    assert "Exports to 10 countries, including 4 regulated markets" in reasons
    assert "Compliance score 90/100" in reasons
    assert "No recall on record" in reasons
    assert "20% market share, 50 years in operation" in reasons
    assert "Tk 10.00/unit, 100% more than the cheapest" in reasons


def test_reasons_for_weak_manufacturer() -> None:
    reasons = rank_brands(GROUP, BOUNDS)[-1].reasons
    assert "Not WHO-GMP certified" in reasons
    assert "No export record" in reasons
    assert "4 recalls on record" in reasons
    assert "Lowest price in this group (Tk 5.00/unit)" in reasons


def test_reasons_use_singular_forms() -> None:
    single = replace(
        C, export_countries=1, regulated_market_exports=1, recall_count=1, years_active=1
    )
    reasons = rank_brands([brand(1, single, "3.00")], BOUNDS)[0].reasons
    assert "Exports to 1 country, including 1 regulated market" in reasons
    assert "1 recall on record" in reasons
    assert "Same price as all alternatives (Tk 3.00/unit)" in reasons
