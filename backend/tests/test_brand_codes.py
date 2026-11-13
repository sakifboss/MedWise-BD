"""R1: stable brand codes in the seed data, the import, the API and the brand index."""

import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import make_engine
from app.models import Brand
from scripts.brand_codes import assign_codes, format_code
from scripts.import_data import run_import

SEED_DIR = get_settings().seed_dir


def rec(name: str, price: float = 1.0, maker: str = "Square", strength: str = "500 mg") -> dict:
    return {
        "name": name,
        "manufacturer": maker,
        "strength": strength,
        "dosage_form": "tablet",
        "price_per_unit": price,
    }


# ---------------------------------------------------------------- assigning codes


def test_first_run_numbers_brands_in_file_order() -> None:
    records, retired = assign_codes([rec("Napa"), rec("Ace"), rec("Renova")], None)
    assert [r["code"] for r in records] == ["BR00001", "BR00002", "BR00003"]
    assert list(records[0])[0] == "code"  # code first, then the rest unchanged
    assert retired == []


def test_codes_survive_price_changes_new_rows_and_removals() -> None:
    first, _ = assign_codes([rec("Napa"), rec("Ace"), rec("Renova")], None)
    previous = {"meta": {"retired_codes": []}, "records": first}
    # Ace removed, Napa's price changed, a new brand added, order changed.
    second, retired = assign_codes([rec("Fast"), rec("Renova"), rec("Napa", price=2.5)], previous)
    codes = {r["name"]: r["code"] for r in second}
    assert codes == {"Napa": "BR00001", "Renova": "BR00003", "Fast": "BR00004"}
    assert retired == ["BR00002"]
    # A retired code is never given out again, even after the brand comes back.
    third, retired = assign_codes(
        [rec("Ace")], {"meta": {"retired_codes": retired}, "records": second}
    )
    assert third[0]["code"] == "BR00005"
    assert retired == ["BR00001", "BR00002", "BR00003", "BR00004"]


def test_identity_ignores_case_and_spaces_but_not_strength_or_maker() -> None:
    first, _ = assign_codes([rec("Napa")], None)
    previous = {"records": first}
    same, _ = assign_codes([rec(" NAPA ", maker=" square ")], previous)
    assert same[0]["code"] == "BR00001"
    other, retired = assign_codes([rec("Napa", strength="665 mg")], previous)
    assert other[0]["code"] == "BR00002" and retired == ["BR00001"]


def test_format() -> None:
    assert format_code(42) == "BR00042"


def test_shipped_brands_all_have_unique_codes() -> None:
    doc = json.loads((SEED_DIR / "brands.json").read_text(encoding="utf-8"))
    codes = [r["code"] for r in doc["records"]]
    assert all(re.fullmatch(r"BR\d{5}", c) for c in codes)
    assert len(set(codes)) == len(codes)
    assert not set(codes) & set(doc["meta"].get("retired_codes", []))
    # New brands go at the end of the sheet, so the import gives existing brands the same database
    # ids as before and old /alternatives/<id> links (from before codes) open the same brand.
    assert codes == sorted(codes)


# ---------------------------------------------------------------- import validation


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    target = tmp_path / "seed"
    shutil.copytree(SEED_DIR, target)
    return target


def _edit_brands(data_dir: Path, change) -> None:
    path = data_dir / "brands.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["records"][1].update(code=d["records"][0]["code"]), "is used twice"),
        (lambda d: d["meta"].update(retired_codes=[d["records"][0]["code"]]), "is retired"),
        (lambda d: d["records"][0].update(code="X1"), "code"),
        (lambda d: d["records"][0].pop("code"), "code"),
    ],
)
def test_bad_codes_are_reported(data_dir: Path, change, message: str) -> None:
    _edit_brands(data_dir, change)
    errors = run_import(data_dir, None, dry_run=True).errors
    assert any(message in e for e in errors), errors


def test_importing_twice_gives_identical_codes(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")

    def codes() -> dict[tuple[str, str, str], str]:
        with Session(engine) as s:
            rows = s.execute(select(Brand.name, Brand.strength, Brand.dosage_form, Brand.code))
            return {(n, st, f): c for n, st, f, c in rows}

    assert run_import(SEED_DIR, engine).ok
    first = codes()
    assert run_import(SEED_DIR, engine).ok
    assert codes() == first and len(first) > 0
    engine.dispose()


# ---------------------------------------------------------------- API


def _seclo(client: TestClient) -> dict:
    hits = client.get("/api/search", params={"q": "Seclo"}).json()["data"]["results"]
    return next(h for h in hits if h["type"] == "brand" and h["name"] == "Seclo")


def test_search_and_alternatives_return_codes(client: TestClient) -> None:
    hit = _seclo(client)
    assert re.fullmatch(r"BR\d{5}", hit["code"])
    by_id = client.get(f"/api/alternatives/{hit['id']}").json()["data"]
    by_code = client.get(f"/api/alternatives/{hit['code']}").json()["data"]
    assert by_code == by_id  # old id links and new code links give the same page
    assert by_code["selected_brand_code"] == hit["code"]
    assert all(re.fullmatch(r"BR\d{5}", a["code"]) for a in by_code["alternatives"])
    lower = client.get(f"/api/alternatives/{hit['code'].lower()}")
    assert lower.status_code == 200


@pytest.mark.parametrize("ref", ["BR99999", "BRX0001", "abc", "0"])
def test_unknown_brand_refs_are_404(client: TestClient, ref: str) -> None:
    assert client.get(f"/api/alternatives/{ref}").status_code == 404


def test_manufacturer_brands_have_codes(client: TestClient) -> None:
    detail = client.get("/api/manufacturers/1").json()["data"]
    assert detail["brands"] and all(b["code"].startswith("BR") for b in detail["brands"])


def test_brand_index(client: TestClient) -> None:
    r = client.get("/api/brands/index")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=3600"
    brands = r.json()["data"]["brands"]
    seed = json.loads((SEED_DIR / "brands.json").read_text(encoding="utf-8"))["records"]
    assert len(brands) == len(seed)
    assert [b["code"] for b in brands] == sorted(b["code"] for b in brands)
    for b in brands:
        assert 1 <= b["rank"] <= b["group_size"]
        assert 0 <= b["approvals"] <= 4
        assert b["price_per_unit"] > 0
    assert len(r.content) < 120_000  # small enough to fetch whole (about 43 KB today)
    # Ranks agree with the ranking page.
    seclo = next(b for b in brands if b["name"] == "Seclo")
    page = client.get(f"/api/alternatives/{seclo['code']}").json()["data"]
    mine = next(a for a in page["alternatives"] if a["code"] == seclo["code"])
    assert (mine["rank"], len(page["alternatives"])) == (seclo["rank"], seclo["group_size"])
