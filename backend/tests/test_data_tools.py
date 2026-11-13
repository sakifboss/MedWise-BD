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
    result = extract(tmp_path, SEED_DIR)
    records, missing, files = result.records, result.missing, result.files
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
    records = extract(tmp_path, seed_copy).records
    doc = {
        "meta": {"dataset": "interactions", "source": "DDInter", "is_sample": False},
        "records": records,
    }
    (seed_copy / "interactions.json").write_text(json.dumps(doc), encoding="utf-8")
    assert run_import(seed_copy, engine=None, dry_run=True).ok


def _seed_doc(seed: Path, name: str) -> dict:
    import json

    return json.loads((seed / f"{name}.json").read_text(encoding="utf-8"))


def _save_doc(seed: Path, name: str, doc: dict) -> None:
    import json

    (seed / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _write_interactions(seed: Path, records: list[dict]) -> None:
    meta = {"dataset": "interactions", "source": "DDInter", "is_sample": False}
    _save_doc(seed, "interactions", {"meta": meta, "records": records})


CHLORAMPHENICOL_ROWS = [
    ["DDInter1", "Chloramphenicol", "DDInter2", "Warfarin", "Moderate"],
    ["DDInter3", "Clopidogrel", "DDInter4", "Omeprazole", "Moderate"],
]


def test_local_only_generic_gets_no_ddinter_pairs(tmp_path: Path, seed_copy: Path) -> None:
    """Chloramphenicol is listed only as eye drops (local): its pairs are left out and reported,
    and the import refuses a pair that slips in anyway."""
    folder = tmp_path / "ddinter"
    folder.mkdir()
    _write_csv(
        folder / "ddinter_downloads_code_S.csv",
        ["DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"],
        CHLORAMPHENICOL_ROWS,
    )
    result = extract(folder, seed_copy)
    assert [(r["generic_a"], r["generic_b"]) for r in result.records] == [
        ("Clopidogrel", "Omeprazole")
    ]
    assert result.left_out == {"Chloramphenicol": (["eye drops"], 1)}

    _write_interactions(seed_copy, result.records)
    assert run_import(seed_copy, engine=None, dry_run=True).ok
    stale = {
        "generic_a": "Chloramphenicol",
        "generic_b": "Warfarin",
        "severity": "moderate",
        "description": "DDInter lists this as a moderate interaction.",
    }
    _write_interactions(seed_copy, [*result.records, stale])
    errors = run_import(seed_copy, engine=None, dry_run=True).errors
    assert any("only as eye drops (a local form)" in e for e in errors), errors


def test_pairs_come_back_when_a_form_taken_by_mouth_is_added(
    tmp_path: Path, seed_copy: Path
) -> None:
    generics = _seed_doc(seed_copy, "generics")
    record = next(g for g in generics["records"] if g["name"] == "Chloramphenicol")
    record["dosage_forms"].append("capsule")
    _save_doc(seed_copy, "generics", generics)
    brands = _seed_doc(seed_copy, "brands")
    brands["records"].append(
        {
            "code": "BR99999",
            "name": "Test Capsule",
            "generic": "Chloramphenicol",
            "manufacturer": "Square Pharmaceuticals PLC",
            "strength": "250 mg",
            "dosage_form": "capsule",
            "price_per_unit": 2.5,
        }
    )
    _save_doc(seed_copy, "brands", brands)

    folder = tmp_path / "ddinter"
    folder.mkdir()
    _write_csv(
        folder / "ddinter_downloads_code_S.csv",
        ["DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"],
        CHLORAMPHENICOL_ROWS,
    )
    result = extract(folder, seed_copy)
    assert ("Chloramphenicol", "Warfarin") in [
        (r["generic_a"], r["generic_b"]) for r in result.records
    ]
    assert result.left_out == {}
    _write_interactions(seed_copy, result.records)
    assert run_import(seed_copy, engine=None, dry_run=True).ok


def test_every_dosage_form_needs_a_route(seed_copy: Path) -> None:
    forms = _seed_doc(seed_copy, "dosage_forms")
    forms["records"] = [f for f in forms["records"] if f["name"] != "eye drops"]
    _save_doc(seed_copy, "dosage_forms", forms)
    errors = run_import(seed_copy, engine=None, dry_run=True).errors
    assert any("unknown dosage form 'eye drops'" in e for e in errors), errors


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


# ---------------------------------------------------------------- Bangla review sheet

from scripts.build_generics_bn import apply_sheet, export_sheet  # noqa: E402


def _sheet_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _approve(rows: list[dict[str, str]], generic: str, field: str, upto: int | None = None) -> None:
    for row in rows:
        if row["generic"] == generic and row["field"] == field:
            if upto is None or int(row["line"]) <= upto:
                row["bangla"], row["approved"] = f"বাংলা {row['line']}", "yes"


def test_fully_approved_field_is_applied_and_partial_is_not(
    tmp_path: Path, seed_copy: Path
) -> None:
    sheet = tmp_path / "bn.csv"
    export_sheet(sheet, seed_copy)
    rows = _sheet_rows(sheet)
    _approve(rows, "Warfarin", "indications")
    _approve(rows, "Warfarin", "side_effects", upto=1)  # only part of the list
    _approve(rows, "Warfarin", "drug_class")
    _write_rows(sheet, rows)

    doc, errors, coverage = apply_sheet(sheet, seed_copy)
    assert errors == []
    warfarin = next(r for r in doc["records"] if r["name"] == "Warfarin")
    assert warfarin["drug_class_bn"] == "বাংলা 1"
    assert warfarin["indications_bn"] == ["বাংলা 1", "বাংলা 2"]
    assert "side_effects_bn" not in warfarin
    assert coverage["indications"] == (1, len(doc["records"]))


def test_stale_and_empty_rows_are_reported(tmp_path: Path, seed_copy: Path) -> None:
    sheet = tmp_path / "bn.csv"
    export_sheet(sheet, seed_copy)
    rows = _sheet_rows(sheet)
    rows[0]["english"] = "Old wording"
    rows[0]["approved"] = "yes"
    rows[1]["approved"] = "yes"  # approved but no Bangla
    _write_rows(sheet, rows)
    _, errors, _ = apply_sheet(sheet, seed_copy)
    assert any("stale" in e for e in errors)
    assert any("Bangla column is empty" in e for e in errors)


def test_export_keeps_existing_translations(tmp_path: Path, seed_copy: Path) -> None:
    sheet = tmp_path / "bn.csv"
    export_sheet(sheet, seed_copy)
    rows = _sheet_rows(sheet)
    rows[0]["bangla"], rows[0]["approved"] = "রাখা হয়েছে", "yes"
    _write_rows(sheet, rows)
    export_sheet(sheet, seed_copy)
    assert _sheet_rows(sheet)[0]["bangla"] == "রাখা হয়েছে"


def test_shipped_review_sheet_matches_generics() -> None:
    sheet = SEED_DIR.parent / "templates" / "generics_bn.csv"
    _, errors, _ = apply_sheet(sheet, SEED_DIR)
    assert errors == []
