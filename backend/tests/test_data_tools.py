"""Tests for the real-data helper scripts (DDInter extraction, brand CSV builder)."""

import csv
import shutil
from pathlib import Path

import pytest

from app.core.config import get_settings
from scripts.build_brands_from_csv import REQUIRED_COLUMNS, build_brands
from scripts.extract_ddinter import extract
from scripts.import_data import run_import

SEED_DIR = get_settings().seed_dir


@pytest.fixture
def seed_copy(tmp_path: Path) -> Path:
    target = tmp_path / "seed"
    shutil.copytree(SEED_DIR, target)
    return target


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------- DDInter


def test_extract_keeps_only_our_generics_and_highest_severity(tmp_path: Path) -> None:
    header = ["DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"]
    _write_csv(
        tmp_path / "ddinter_downloads_code_B.csv",
        header,
        [
            ["DDInter1", "Warfarin", "DDInter2", "Acetylsalicylic acid", "Moderate"],
            ["DDInter2", "Acetylsalicylic acid", "DDInter1", "Warfarin", "Major"],
            ["DDInter1", "Warfarin", "DDInter9", "Some other drug", "Major"],
            ["DDInter3", "Clopidogrel", "DDInter4", "Omeprazole", "Unknown"],
        ],
    )
    _write_csv(
        tmp_path / "ddinter_downloads_code_N.csv",
        header,
        [["DDInter5", "Acetaminophen", "DDInter1", "Warfarin", "Minor"]],
    )
    records, missing, files = extract(tmp_path, SEED_DIR)
    assert files == 2
    assert [(r["generic_a"], r["generic_b"], r["severity"]) for r in records] == [
        ("Aspirin", "Warfarin", "major"),
        ("Paracetamol", "Warfarin", "minor"),
    ]
    assert "Metformin" in missing


def test_extract_output_passes_seed_validation(tmp_path: Path, seed_copy: Path) -> None:
    import json

    _write_csv(
        tmp_path / "ddinter_downloads_code_C.csv",
        ["DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"],
        [["DDInter1", "Clopidogrel", "DDInter2", "Omeprazole", "Moderate"]],
    )
    records, _, _ = extract(tmp_path, seed_copy)
    doc = {
        "meta": {"dataset": "interactions", "source": "DDInter", "is_sample": False},
        "records": records,
    }
    (seed_copy / "interactions.json").write_text(json.dumps(doc), encoding="utf-8")
    assert run_import(seed_copy, engine=None, dry_run=True).ok


# ---------------------------------------------------------------- brands CSV


def test_build_brands_valid_rows_and_skips_blank(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "brands.csv",
        list(REQUIRED_COLUMNS),
        [
            [
                "Ace",
                "Paracetamol",
                "500MG",
                "Tablet",
                "Square Pharmaceuticals PLC",
                "1.20",
                "https://example.com/ace",
            ],
            ["", "Paracetamol", "500 mg", "tablet", "", "", ""],
        ],
    )
    records, errors = build_brands(path, SEED_DIR)
    assert errors == []
    assert records == [
        {
            "name": "Ace",
            "generic": "Paracetamol",
            "manufacturer": "Square Pharmaceuticals PLC",
            "strength": "500 mg",
            "dosage_form": "tablet",
            "price_per_unit": 1.2,
            "source_url": "https://example.com/ace",
        }
    ]


def test_build_brands_reports_every_problem(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "brands.csv",
        list(REQUIRED_COLUMNS),
        [["X", "Unobtainium", "5 mg", "tablet", "Nobody Ltd", "abc", "not a link"]],
    )
    _, errors = build_brands(path, SEED_DIR)
    text = " ".join(errors)
    assert "unknown generic" in text
    assert "unknown manufacturer" in text
    assert "not positive" in text
    assert "must be a link" in text


def test_build_brands_requires_columns(tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "brands.csv", ["brand_name"], [["Ace"]])
    _, errors = build_brands(path, SEED_DIR)
    assert errors and "missing column" in errors[0]


def test_shipped_template_has_required_columns() -> None:
    template = SEED_DIR.parent / "templates" / "brands_template.csv"
    with template.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle))
    assert set(REQUIRED_COLUMNS) <= set(header)
