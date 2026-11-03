"""Unit tests for app/services/ranking.py.

Hand-worked example (bounds come from manufacturers A, B, C):
    A: all 4 regulators, best on the rest -> C=1,   E=1,   R=1,   H=0,   M=1   -> Q = 1.00
    B: no approvals, worst on the rest    -> C=0,   E=0,   R=0,   H=1,   M=0   -> Q = 0.00
    C: 2 of 4 regulators, midway          -> C=0.5, E=0.5, R=0.5, H=0.5, M=0.5 -> Q = 0.50
    Prices A=10, B=5, C=7.5               -> P_A=0, P_B=1, P_C=0.5
    Final = 100*(0.8Q + 0.2P)             -> A=80, C=50, B=20
R is the absolute compliance score / 100 (A=100, B=0, C=50).
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

ALL_FOUR = ("US FDA", "UK MHRA", "EU GMP", "TGA Australia")
A = ManufacturerFactors(1, "Alpha", ALL_FOUR, 10, 4, 100, 0, 20, 50)
B = ManufacturerFactors(2, "Beta", (), 0, 0, 0, 4, 0, 10)
C = ManufacturerFactors(3, "Gamma", ("US FDA", "UK MHRA"), 5, 2, 50, 2, 10, 30)
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
    assert c.certification == pytest.approx(0.5)
    assert c.export == pytest.approx(0.5)
    assert c.compliance == pytest.approx(0.5)
    assert c.recall_history == pytest.approx(0.5)
    assert c.market == pytest.approx(0.5)


@pytest.mark.parametrize(("m", "expected"), [(A, 1.0), (B, 0.0), (C, 0.5)])
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
    assert final_score(0.5, 0.5) == pytest.approx(50.0)
    assert final_score(1.0, 1.0) == pytest.approx(100.0)
    assert final_score(0.0, 0.0) == 0.0


# ---------------------------------------------------------------- rank_brands


def test_rank_brands_hand_example() -> None:
    ranked = rank_brands(GROUP, BOUNDS)
    assert [r.candidate.brand_id for r in ranked] == [1, 3, 2]
    assert [r.rank for r in ranked] == [1, 2, 3]
    assert [r.final_score for r in ranked] == pytest.approx([80.0, 50.0, 20.0])
    assert [r.price_score for r in ranked] == pytest.approx([0.0, 0.5, 1.0])


def test_quality_outweighs_price() -> None:
    # Best manufacturer at 10x the price still beats the worst one at the lowest price.
    ranked = rank_brands([brand(1, A, "50.00"), brand(2, B, "5.00")], BOUNDS)
    assert ranked[0].candidate.brand_id == 1


def test_quality_does_not_depend_on_group() -> None:
    alone = rank_brands([brand(3, C, "7.50")], BOUNDS)[0]
    assert alone.quality_score == pytest.approx(0.5)
    assert alone.price_score == 1.0  # only brand -> all prices equal
    assert alone.final_score == pytest.approx(100 * (0.8 * 0.5 + 0.2))


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
    assert "Has plant(s) approved by US FDA, UK MHRA, EU GMP, TGA Australia" in reasons
    assert "Exports to 10 countries, including 4 regulated markets" in reasons
    assert "Compliance score 100/100" in reasons
    assert "No recall on record" in reasons
    assert "20% market share, 50 years in operation" in reasons
    assert "Tk 10.00/unit, 100% more than the cheapest" in reasons


def test_reasons_for_weak_manufacturer() -> None:
    reasons = rank_brands(GROUP, BOUNDS)[-1].reasons
    assert "No US FDA, UK MHRA, EU GMP or TGA plant approval found" in reasons
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


# ---------------------------------------------------------------- real-data edge cases


def test_certification_counts_each_regulator_once_and_ignores_unknown() -> None:
    m = replace(C, stringent_approvals=("US FDA", "US FDA", "WHO-GMP"))
    assert quality_components(m, BOUNDS).certification == pytest.approx(0.25)


def test_certification_reason_uses_canonical_order() -> None:
    m = replace(C, stringent_approvals=("TGA Australia", "US FDA"))
    reasons = rank_brands([brand(1, m, "1.00")], BOUNDS)[0].reasons
    assert "Has plant(s) approved by US FDA, TGA Australia" in reasons


def test_unknown_market_share_scores_as_zero_and_is_explained() -> None:
    unknown = replace(C, market_share=None)
    assert quality_components(unknown, BOUNDS).market == pytest.approx(
        0.5 * 0.0 + 0.5 * normalize(30, *BOUNDS["years_active"])
    )
    reasons = rank_brands([brand(1, unknown, "1.00")], BOUNDS)[0].reasons
    assert "30 years in operation (market share not available)" in reasons


def test_bounds_handle_unknown_market_share() -> None:
    bounds = compute_bounds([A, replace(B, market_share=None)])
    assert bounds["market_share"] == (0.0, 20.0)


def test_missing_recall_data_is_explained_not_claimed_clean() -> None:
    m = replace(A, recall_data_available=False)
    reasons = rank_brands([brand(1, m, "1.00")], BOUNDS)[0].reasons
    assert "Recall history not available" in reasons
    assert "No recall on record" not in reasons


def test_compliance_is_absolute_not_relative() -> None:
    # One company at 85 among companies at 100 keeps 0.85, not 0.
    m = replace(A, compliance_score=85)
    assert quality_components(m, BOUNDS).compliance == pytest.approx(0.85)


# ---------------------------------------------------------------- Bangla reasons


def test_bangla_reasons_carry_the_same_facts() -> None:
    best = rank_brands(GROUP, BOUNDS, lang="bn")[0].reasons
    assert best[0] == "US FDA, UK MHRA, EU GMP, TGA Australia-এর অনুমোদিত প্ল্যান্ট আছে"
    assert best[1] == "১০টি দেশে রপ্তানি করে, এর মধ্যে ৪টি নিয়ন্ত্রিত বাজার"
    assert "কমপ্লায়েন্স স্কোর ১০০/১০০" in best
    assert "কোনো রিকলের রেকর্ড নেই" in best
    assert "৳১০.০০/ইউনিট, সবচেয়ে সস্তাটির চেয়ে ১০০% বেশি" in best
    worst = rank_brands(GROUP, BOUNDS, lang="bn")[-1].reasons
    assert "রপ্তানির কোনো তথ্য নেই" in worst
    assert "এই গ্রুপে সবচেয়ে কম দাম (৳৫.০০/ইউনিট)" in worst


def test_bangla_never_claims_clean_recall_when_data_is_missing() -> None:
    m = replace(A, recall_data_available=False, market_share=None)
    reasons = rank_brands([brand(1, m, "1.00")], BOUNDS, lang="bn")[0].reasons
    assert "রিকলের ইতিহাস পাওয়া যায়নি" in reasons
    assert "কোনো রিকলের রেকর্ড নেই" not in reasons
    assert "৫০ বছর ধরে চালু (বাজারের অংশ জানা নেই)" in reasons


def test_language_does_not_change_scores() -> None:
    en = rank_brands(GROUP, BOUNDS)
    bn = rank_brands(GROUP, BOUNDS, lang="bn")
    assert [(r.candidate.brand_id, r.final_score) for r in en] == [
        (r.candidate.brand_id, r.final_score) for r in bn
    ]
