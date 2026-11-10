"""P10 step A: red flags and specialties seed files, their validation, and the Bangla sheet."""

import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.schemas.seed import REQUIRED_SPECIALTIES
from scripts.build_symptoms_bn import apply_sheet, export_sheet, read_sheet, write_sheet
from scripts.import_data import run_import

SEED_DIR = get_settings().seed_dir
# The guide never names a disease (Claude.MD, P10): these must not appear in what it shows.
DISEASE_WORDS = re.compile(
    r"stroke|sepsis|heart attack|anaphyla|epilep|meningitis|asthma|covid|cancer|diabet|"
    r"infection|disease|syndrome|allerg",
    re.I,
)


def _doc(name: str) -> dict[str, Any]:
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    target = tmp_path / "seed"
    shutil.copytree(SEED_DIR, target)
    return target


def _edit(data_dir: Path, dataset: str, change) -> None:
    path = data_dir / f"{dataset}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc["records"])
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _errors(data_dir: Path) -> list[str]:
    return run_import(data_dir, None, dry_run=True).errors


def test_shipped_files_are_valid() -> None:
    result = run_import(SEED_DIR, None, dry_run=True)
    assert result.ok, result.errors
    assert result.counts["red_flags"] > 0 and result.counts["specialties"] >= 3


def test_red_flags_are_from_nhs_and_never_name_a_disease() -> None:
    for row in _doc("red_flags")["records"]:
        assert row["source_url"].startswith("https://www.nhs.uk/")
        assert not DISEASE_WORDS.search(row["text"]), row["text"]


def test_specialties_describe_body_areas_not_diseases() -> None:
    ids = {s["id"] for s in _doc("specialties")["records"]}
    assert set(REQUIRED_SPECIALTIES) <= ids
    for s in _doc("specialties")["records"]:
        assert not DISEASE_WORDS.search(f"{s['name']} {s['covers']}"), s["id"]


@pytest.mark.parametrize(
    ("dataset", "change", "message"),
    [
        ("red_flags", lambda r: r[0].update(source_url="https://example.com/x"), "source_url"),
        ("red_flags", lambda r: r[0].update(group="rash"), "group"),
        ("red_flags", lambda r: r[1].update(id=r[0]["id"]), "duplicate id"),
        ("red_flags", lambda r: r.append({**r[0], "id": "chest-99"}), "same text twice"),
        ("red_flags", lambda r: r[0].update(advice="take aspirin"), "advice"),
        ("specialties", lambda r: r.pop(0), "'general_medicine' is required"),
        ("specialties", lambda r: r[0].update(id="General Medicine"), "id"),
    ],
)
def test_bad_rows_are_reported(data_dir: Path, dataset: str, change, message: str) -> None:
    _edit(data_dir, dataset, change)
    errors = _errors(data_dir)
    assert any(message in e for e in errors), errors


def test_bangla_sheet_applies_only_approved_rows(data_dir: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "symptoms_bn.csv"
    total = export_sheet(sheet, data_dir)
    rows = read_sheet(sheet)
    assert len(rows) == total
    rows[0].update(bangla="অনুবাদ", approved="yes")  # first red flag
    rows[1].update(bangla="খসড়া")  # drafted, not approved
    write_sheet(sheet, rows)
    docs, problems, applied = apply_sheet(sheet, data_dir)
    assert problems == [] and applied == 1
    flags = docs["red_flags"]["records"]
    assert flags[0]["text_bn"] == "অনুবাদ"
    assert flags[1]["text_bn"] is None


def test_bangla_sheet_refuses_stale_rows(data_dir: Path, tmp_path: Path) -> None:
    sheet = tmp_path / "symptoms_bn.csv"
    export_sheet(sheet, data_dir)
    _edit(data_dir, "red_flags", lambda r: r[0].update(text="changed NHS wording"))
    docs, problems, _ = apply_sheet(sheet, data_dir)
    assert any("stale" in p for p in problems)
    # Export again keeps the other rows and adds the changed one empty.
    export_sheet(sheet, data_dir)
    with sheet.open(encoding="utf-8-sig") as handle:
        changed = [r for r in csv.DictReader(handle) if r["english"] == "changed NHS wording"]
    assert changed and changed[0]["bangla"] == ""


def test_shipped_sheet_covers_every_text() -> None:
    sheet = SEED_DIR.parent / "templates" / "symptoms_bn.csv"
    rows = read_sheet(sheet)
    flags, specialties = _doc("red_flags")["records"], _doc("specialties")["records"]
    assert len(rows) == len(flags) + 2 * len(specialties)
    assert all(r["bangla"] for r in rows), "every row has a Bangla draft for review"
