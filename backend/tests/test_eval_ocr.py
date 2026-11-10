"""Scoring code of scripts/eval_ocr.py, with fake extractions (no network, no Gemini)."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from app.services.ocr import ExtractedMedicine as E
from scripts.eval_ocr import (
    APP_MAX_SIDE,
    Expected,
    ImageResult,
    Suggestion,
    TruthMedicine,
    catalog_lookup,
    dedupe,
    load_truth,
    load_unreadable,
    name_score,
    norm_name,
    pair_names,
    prepare_image,
    read_cache,
    results_markdown,
    score_matching,
    score_reading,
    strengths_agree,
    totals_by_subset,
    write_cache,
)

T = TruthMedicine

# ---------------------------------------------------------------- names and strengths


def test_names_ignore_case_spaces_dots_and_hyphens() -> None:
    assert norm_name("Ace Plus") == norm_name("AcePlus") == norm_name("ace-plus")
    assert name_score("Ace Plus", "AcePlus") == 100


@pytest.mark.parametrize(
    ("a", "b", "agree"),
    [
        ("500 mg", "500mg", True),
        ("500 mg", "500", True),  # doctors often write the number only
        ("20", "20 mg", True),
        ("2.5 mg", "2.50 mg", True),
        ("2%", "2 %", True),
        ("500 mg", "250 mg", False),
        ("10 mg", "10 ml", False),
        (None, "500 mg", True),  # compared only when both sides have one
        ("500 mg", None, True),
    ],
)
def test_strengths_agree(a: str | None, b: str | None, agree: bool) -> None:
    assert strengths_agree(a, b) is agree


def test_dedupe_keeps_one_per_name_and_prefers_a_strength() -> None:
    meds = [E("Ace", None), E("ACE", "500 mg"), E("Fexo", "120 mg"), E("fexo", None)]
    assert dedupe(meds) == [E("ACE", "500 mg"), E("Fexo", "120 mg")]


# ---------------------------------------------------------------- reading


def test_pairs_are_one_to_one_and_best_first() -> None:
    truth = [T("DemoMed-B", None), T("DemoMed-C", None)]
    extracted = [E("DemoMed-C", None), E("DemoMed-B", None)]
    pairs = pair_names(truth, extracted, 85)
    assert [(p.truth, p.extracted, p.score) for p in pairs] == [(0, 1, 100), (1, 0, 100)]


def test_reading_counts_correct_missed_extra_and_wrong_strength() -> None:
    truth = [T("Ace", "500 mg"), T("Fexo", "120 mg"), T("Monas", "10 mg")]
    extracted = [E("Ace", "500 mg"), E("Fexo", "180 mg"), E("Napa", None)]
    r = score_reading(truth, extracted, 85)
    assert [p.truth for p in r.correct] == [0]
    assert [p.truth for p in r.wrong_strength] == [1]
    assert r.missed == [2]
    assert r.extra == [2]


def test_threshold_is_configurable() -> None:
    truth = [T("Montene", None)]
    extracted = [E("Montine", None)]  # one letter off: ratio 85.7
    assert len(score_reading(truth, extracted, 85).correct) == 1
    assert score_reading(truth, extracted, 90).missed == [0]


def test_close_names_are_flagged_for_review() -> None:
    r = score_reading([T("DemoMed-A", None)], [E("DemoMed-B", None)], 85)
    assert len(r.correct) == 1  # "demomeda" vs "demomedb" = 87.5: above the threshold ...
    assert [p.score for p in r.inexact] == [87.5]  # ... but flagged


# ---------------------------------------------------------------- matching

BRANDS = {"ace": {"Paracetamol"}, "nexummups": {"Esomeprazole"}, "montene": {"Montelukast"}}
GENERICS = {
    "paracetamol": "Paracetamol",
    "esomeprazole": "Esomeprazole",
    "montelukast": "Montelukast",
}
LOOKUP = catalog_lookup(BRANDS, GENERICS)


def test_catalog_lookup_by_brand_generic_name_or_explicit_generic() -> None:
    assert LOOKUP(T("Ace", "500 mg")) == Expected("Paracetamol", "500 mg")
    assert LOOKUP(T("paracetamol", None)) == Expected("Paracetamol", None)
    # The catalog calls it "Nexum MUPS"; the ground truth names the generic explicitly.
    assert LOOKUP(T("Nexum", "20 mg", generic="Esomeprazole")) == Expected("Esomeprazole", "20 mg")
    assert LOOKUP(T("Fexo", "120 mg")) is None


def test_matching_counts_only_catalog_medicines() -> None:
    truth = [
        T("Ace", "500 mg"),
        T("Fexo", "120 mg"),
        T("Montene", None),
        T("Nexum", "20", "Esomeprazole"),
    ]
    extracted = [E("Ace", "500 mg"), E("Fexo", "120 mg"), E("Montene", "10 mg")]
    reading = score_reading(truth, extracted, 85)
    suggestions = [
        Suggestion("Paracetamol", "500 mg"),
        None,
        Suggestion("Montelukast", "10 mg"),  # truth has no strength: any strength is right
    ]
    m = score_matching(truth, reading, suggestions, LOOKUP)
    assert (m.in_catalog, m.matched) == (3, 2)
    assert m.failures == ["Nexum: not read"]


def test_matching_failures_name_the_reason() -> None:
    truth = [T("Ace", "500 mg"), T("Montene", "10 mg")]
    extracted = [E("Ace", "500 mg"), E("Montene", "10 mg")]
    reading = score_reading(truth, extracted, 85)
    suggestions = [Suggestion("Paracetamol", "120 mg/5 ml"), None]
    m = score_matching(truth, reading, suggestions, LOOKUP)
    assert m.matched == 0
    assert m.failures == ["Ace: suggested Paracetamol 120 mg/5 ml", "Montene: no suggestion"]


# ---------------------------------------------------------------- totals and report


def _result(
    image_id: str, subset: str, truth: list[TruthMedicine], extracted: list[E]
) -> ImageResult:
    reading = score_reading(truth, extracted, 85)
    matching = score_matching(truth, reading, [None] * len(extracted), LOOKUP)
    return ImageResult(image_id, subset, truth, extracted, reading, matching, "model-x")


def test_totals_per_subset_and_overall() -> None:
    results = [
        _result("rx01", "real_handwritten", [T("Ace", None), T("Fexo", None)], [E("Ace", None)]),
        _result(
            "rx11",
            "synthetic_printed",
            [T("DemoMed-A", None)],
            [E("DemoMed-A", None), E("X", None)],
        ),
    ]
    totals = totals_by_subset(results)
    assert totals["real_handwritten"].recall == 0.5
    assert totals["real_handwritten"].precision == 1.0
    assert totals["synthetic_printed"].precision == 0.5
    assert totals["synthetic_printed"].match_rate is None  # nothing in the catalog
    assert (totals["overall"].correct, totals["overall"].truth, totals["overall"].extracted) == (
        2,
        3,
        3,
    )


def test_results_markdown_has_totals_notes_and_exclusions() -> None:
    results = [_result("rx11", "synthetic_printed", [T("DemoMed-A", None)], [E("DemoMed-A", None)])]
    md = results_markdown(results, 85, {"reason": "Kexam on rx07 and rx08: unreadable."})
    assert "| synthetic_printed | 1 | 1 | 1 | 1 | 100.0% | 100.0% | 0/0 | n/a | 0/0 | n/a |" in md
    assert "fictional medicine names" in md
    assert "Not scored: Kexam on rx07 and rx08" in md
    assert "model-x (1)" in md


# ---------------------------------------------------------------- files


def test_load_truth_reads_optional_generic(tmp_path: Path) -> None:
    path = tmp_path / "rx01.json"
    path.write_text(
        json.dumps(
            {
                "medicines": [
                    {"name": "Nexum", "strength": "20 mg", "generic": "Esomeprazole"},
                    {"name": "Ace", "strength": None},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_truth(path) == [T("Nexum", "20 mg", "Esomeprazole"), T("Ace", None)]


def test_cache_round_trip_and_invalidation(tmp_path: Path) -> None:
    path = tmp_path / "cache" / "rx01.json"
    write_cache(path, "hash-1", [E("Ace", "500 mg")], "model-x")
    assert read_cache(path, "hash-1") == ([E("Ace", "500 mg")], "model-x")
    assert read_cache(path, "hash-2") is None  # the photo changed
    assert read_cache(tmp_path / "missing.json", "hash-1") is None


def test_prepare_image_resizes_like_the_app() -> None:
    raw = io.BytesIO()
    Image.new("RGB", (4000, 3000), "white").save(raw, "PNG")
    sent = prepare_image(raw.getvalue())
    with Image.open(io.BytesIO(sent)) as image:
        assert image.format == "JPEG"
        assert image.size == (APP_MAX_SIDE, 1500)

    small = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(small, "PNG")
    with Image.open(io.BytesIO(prepare_image(small.getvalue()))) as image:
        assert image.size == (800, 600)  # never enlarged


# ---------------------------------------------------------------- added after the first real run


@pytest.mark.parametrize(
    ("read", "truth"),
    [
        ("Benostar mouthwash", "Benostar"),
        ("Viodin M/W", "Viodin"),
        ("Tab. Ace", "Ace"),
        ("Syp Ambrox", "Ambrox"),
    ],
)
def test_dosage_form_words_are_ignored_in_names(read: str, truth: str) -> None:
    assert name_score(read, truth) == 100


def test_a_name_that_is_only_a_form_word_is_kept() -> None:
    assert norm_name("Gel") == "gel"


def test_reads_of_unreadable_lines_do_not_count_against_precision() -> None:
    truth = [T("Ace", None), T("Romycin", "500 mg")]
    extracted = [E("Ace", None), E("Romycin", "500"), E("Kexami", None)]
    r = score_reading(truth, extracted, 85, unreadable=1)
    assert r.extra == []
    assert r.unscored == [2]
    assert r.scored_extracted == 2


def test_unreadable_lines_take_the_least_similar_extras() -> None:
    truth = [T("Montene", None)]
    extracted = [E("Montek", None), E("Kexami", None)]  # Montek: a misread of Montene
    r = score_reading(truth, extracted, 90, unreadable=1)
    assert r.missed == [0]
    assert [extracted[i].name for i in r.unscored] == ["Kexami"]
    assert [extracted[i].name for i in r.extra] == ["Montek"]


def test_offered_counts_the_right_option_even_without_a_suggestion() -> None:
    truth = [T("Nexum", "20 mg", "Esomeprazole")]
    extracted = [E("Nexum", "20 mg")]
    reading = score_reading(truth, extracted, 85)
    offered = [[Suggestion("Esomeprazole", "40 mg"), Suggestion("Esomeprazole", "20 mg")]]
    m = score_matching(truth, reading, [None], LOOKUP, offered)
    assert (m.matched, m.offered) == (0, 1)
    assert m.failures == ["Nexum: no suggestion (right option listed)"]


def test_load_unreadable(tmp_path: Path) -> None:
    with_lines = tmp_path / "a.json"
    with_lines.write_text(json.dumps({"medicines": [], "unreadable": 1}), encoding="utf-8")
    without = tmp_path / "b.json"
    without.write_text(json.dumps({"medicines": []}), encoding="utf-8")
    assert (load_unreadable(with_lines), load_unreadable(without)) == (1, 0)
