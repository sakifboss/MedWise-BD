import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import make_engine
from app.models import Brand, Generic, Interaction, Manufacturer
from app.schemas.seed import normalize_strength
from scripts.import_data import main, run_import

SEED_DIR = get_settings().seed_dir


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    target = tmp_path / "seed"
    shutil.copytree(SEED_DIR, target)
    return target


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")


def _edit(data_dir: Path, dataset: str, change: Any) -> None:
    path = data_dir / f"{dataset}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc["records"])
    path.write_text(json.dumps(doc), encoding="utf-8")


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def _records(name: str) -> list:
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))["records"]


def test_shipped_seed_data_is_valid() -> None:
    result = run_import(SEED_DIR, engine=None, dry_run=True)
    assert result.errors == []
    assert result.counts["manufacturers"] == 13
    assert result.counts["generics"] == len(_records("generics"))
    assert result.counts["brands"] >= 40
    assert result.counts["interactions"] >= 1
    # Manufacturer quality data is real (sourced), not sample.
    assert "manufacturers" not in result.sample_datasets
    assert "quality_factors" not in result.sample_datasets
    # No dataset is sample any more.
    assert result.sample_datasets == []


def test_import_writes_all_rows(data_dir: Path, engine: Engine) -> None:
    result = run_import(data_dir, engine)
    assert result.ok
    assert _count(engine, Manufacturer) == result.counts["manufacturers"]
    assert _count(engine, Generic) == result.counts["generics"]
    assert _count(engine, Brand) == result.counts["brands"]
    assert _count(engine, Interaction) == result.counts["interactions"]


def test_quality_factors_are_merged_into_manufacturers(data_dir: Path, engine: Engine) -> None:
    run_import(data_dir, engine)
    with Session(engine) as session:
        square = session.scalars(
            select(Manufacturer).where(Manufacturer.name == "Square Pharmaceuticals PLC")
        ).one()
    assert "US FDA" in square.stringent_approvals
    assert square.compliance_score > 0
    assert square.export_country_total > 0
    assert square.recall_data_available is False
    assert all(url.startswith("http") for url in square.source_urls)


def test_reimport_replaces_instead_of_duplicating(data_dir: Path, engine: Engine) -> None:
    first = run_import(data_dir, engine)
    run_import(data_dir, engine)
    assert _count(engine, Manufacturer) == first.counts["manufacturers"]
    assert _count(engine, Interaction) == first.counts["interactions"]


def test_interaction_pairs_stored_in_id_order(data_dir: Path, engine: Engine) -> None:
    run_import(data_dir, engine)
    with Session(engine) as session:
        pairs = session.execute(select(Interaction.generic_a_id, Interaction.generic_b_id)).all()
    assert all(a < b for a, b in pairs)


def test_failed_import_leaves_existing_data_untouched(data_dir: Path, engine: Engine) -> None:
    run_import(data_dir, engine)
    brands_before = _count(engine, Brand)

    def typo(records: list[dict]) -> None:
        records[0]["generic"] = "Paracetmol"
        records.pop()

    _edit(data_dir, "brands", typo)
    result = run_import(data_dir, engine)
    assert not result.ok
    assert any("unknown generic 'Paracetmol'" in e and "Paracetamol" in e for e in result.errors)
    assert _count(engine, Brand) == brands_before


def test_bad_row_values_are_reported_with_location(data_dir: Path) -> None:
    def break_rows(records: list[dict]) -> None:
        records[2]["price_per_unit"] = -5
        records[3]["strength"] = "lots"

    _edit(data_dir, "brands", break_rows)
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any(e.startswith("brands.json[2]") and "price_per_unit" in e for e in errors)
    assert any(e.startswith("brands.json[3]") and "strength" in e for e in errors)


def test_reversed_duplicate_interaction_is_rejected(data_dir: Path) -> None:
    def add_reverse(records: list[dict]) -> None:
        first = records[0]
        records.append({**first, "generic_a": first["generic_b"], "generic_b": first["generic_a"]})

    _edit(data_dir, "interactions", add_reverse)
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any("duplicate pair" in e for e in errors)


def test_dosage_form_must_match_generic(data_dir: Path) -> None:
    def wrong_form(records: list[dict]) -> None:
        records[0]["dosage_form"] = "injection"

    _edit(data_dir, "brands", wrong_form)
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any("dosage form 'injection' not listed" in e for e in errors)


def test_manufacturer_without_quality_factors_is_rejected(data_dir: Path) -> None:
    _edit(data_dir, "quality_factors", lambda records: records.pop())
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any("no entry in quality_factors.json" in e for e in errors)


def test_unknown_fields_are_rejected(data_dir: Path) -> None:
    def extra(records: list[dict]) -> None:
        records[0]["pricee"] = 1

    _edit(data_dir, "brands", extra)
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any("pricee" in e for e in errors)


def test_missing_file_is_reported(data_dir: Path) -> None:
    (data_dir / "generics.json").unlink()
    errors = run_import(data_dir, engine=None, dry_run=True).errors
    assert any("generics.json: file not found" in e for e in errors)


def test_cli_exit_codes(data_dir: Path, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    assert main(["--data-dir", str(data_dir), "--database-url", url]) == 0
    _edit(data_dir, "brands", lambda records: records[0].update(price_per_unit=0))
    assert main(["--data-dir", str(data_dir), "--dry-run"]) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("500mg", "500 mg"),
        ("500 MG", "500 mg"),
        ("120mg / 5mL", "120 mg/5 ml"),
        ("  10  mg ", "10 mg"),
        ("500mg+125mg", "500 mg + 125 mg"),
    ],
)
def test_normalize_strength(raw: str, expected: str) -> None:
    assert normalize_strength(raw) == expected


def test_unknown_regulator_is_rejected(data_dir: Path) -> None:
    _edit(data_dir, "quality_factors", lambda rows: rows[0].update(stringent_approvals=["WHO"]))
    result = run_import(data_dir, engine=None, dry_run=True)
    assert not result.ok
    assert any("stringent_approvals" in e for e in result.errors)


def test_source_urls_must_be_links(data_dir: Path) -> None:
    _edit(data_dir, "quality_factors", lambda rows: rows[0].update(source_urls=["company site"]))
    result = run_import(data_dir, engine=None, dry_run=True)
    assert not result.ok
    assert any("source_urls" in e for e in result.errors)


def test_generic_source_urls_must_be_links(data_dir: Path) -> None:
    _edit(data_dir, "generics", lambda rows: rows[0].update(source_urls=["NHS"]))
    result = run_import(data_dir, engine=None, dry_run=True)
    assert not result.ok
    assert any("source_urls" in e for e in result.errors)


def test_unknown_market_share_is_allowed(data_dir: Path) -> None:
    _edit(data_dir, "quality_factors", lambda rows: rows[0].update(market_share=None))
    assert run_import(data_dir, engine=None, dry_run=True).ok


def test_bangla_list_must_translate_every_line(data_dir: Path) -> None:
    _edit(data_dir, "generics", lambda rows: rows[0].update(indications_bn=["শুধু একটি"]))
    result = run_import(data_dir, engine=None, dry_run=True)
    assert not result.ok
    assert any("translate every line" in e for e in result.errors)
