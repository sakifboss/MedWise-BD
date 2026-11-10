"""Scoring code of scripts/eval_symptoms.py (no network, no Gemini)."""

from collections import Counter
from datetime import date
from pathlib import Path

from scripts.eval_symptoms import Case, Outcome, load_cases, results_markdown, totals

ANSWERS = {
    "text": "x x x",
    "since": "days",
    "severity": "mild",
    "age_group": "adult",
    "pregnant": "no",
}


def case(cid: str, red: bool, specialty: tuple[str, ...] = (), lang: str = "en") -> Case:
    return Case(cid, lang, {**ANSWERS, "lang": "en"}, red, specialty)


def test_scoring_counts_recall_false_alarms_and_accuracy() -> None:
    outcomes = [
        Outcome(case("rf1", True), True, None, "ok", "m"),
        Outcome(case("rf2", True), False, "general_medicine", "ok", "m"),  # missed emergency
        Outcome(case("sp1", False, ("eye",)), False, "eye", "ok", "m"),
        Outcome(
            case("sp2", False, ("eye", "general_medicine")), False, "general_medicine", "dose", "m"
        ),
        Outcome(case("sp3", False, ("dental",)), True, None, "ok", "m"),  # false alarm
        Outcome(case("sp4", False, ("ent",)), False, "dermatology", "ok", "m"),
    ]
    t = totals(outcomes)
    assert (t.red_caught, t.red_cases, t.red_recall) == (1, 2, 0.5)
    assert (t.false_alarms, t.specialty_right, t.ordinary) == (1, 2, 4)
    md = results_markdown(outcomes, Counter({"m": 6}), date(2026, 11, 10))
    assert "Red-flag recall is below 100%" in md
    assert "rf2 [en] want emergency, got general_medicine" in md
    assert "sp3 [en] want dental, got emergency" in md


def test_unanswered_cases_are_reported() -> None:
    outcomes = [
        Outcome(case("rf1", True), False, "general_medicine", "ai_unavailable", None, "HTTP 503")
    ]
    assert totals(outcomes).unanswered == 1
    assert "got no model answer; run again" in results_markdown(
        outcomes, Counter(), date(2026, 11, 10)
    )


def test_shipped_cases_load_and_include_every_language_and_red_flags() -> None:
    cases = load_cases(Path(__file__).resolve().parents[2] / "data" / "eval" / "symptoms.json")
    assert len(cases) >= 40 - 1
    assert {c.lang for c in cases} == {"en", "bn", "banglish"}
    assert sum(c.red_flag for c in cases) >= 10
    assert all(c.specialty for c in cases if not c.red_flag)
    assert len({c.id for c in cases}) == len(cases)
