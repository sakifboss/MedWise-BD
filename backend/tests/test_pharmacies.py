"""P9 pharmacy finder: seed validation, which phone numbers are stored, the API and its limit."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import make_engine
from app.models import Pharmacy
from app.schemas.seed import SYLHET_BBOX
from scripts.fetch_osm_pharmacies import build_pharmacies, exclusion_reason, keep_hand_fields
from scripts.import_data import distance_metres, run_import

SEED_DIR = get_settings().seed_dir
ZINDABAZAR = (24.8967, 91.8710)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    target = tmp_path / "seed"
    shutil.copytree(SEED_DIR, target)
    return target


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")


def _pharmacy(**fields: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": "Test Pharmacy",
        "lat": ZINDABAZAR[0],
        "lon": ZINDABAZAR[1],
        "source": "osm",
        "osm_type": "node",
        "osm_id": 9_000_000_001,
    }
    return {**row, **fields}


def _set_pharmacies(data_dir: Path, rows: list[dict[str, Any]]) -> None:
    path = data_dir / "pharmacies.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["records"] = rows
    path.write_text(json.dumps(doc), encoding="utf-8")


def _errors(data_dir: Path) -> list[str]:
    return run_import(data_dir, None, dry_run=True).errors


# ---------------------------------------------------------------- import validation


def test_shipped_pharmacy_data_is_valid() -> None:
    result = run_import(SEED_DIR, None, dry_run=True)
    assert result.ok, result.errors
    assert result.counts["pharmacies"] > 0
    assert result.counts["sylhet_areas"] > 0


def test_shipped_pharmacies_are_real_osm_places_and_nobody_is_a_partner_yet() -> None:
    doc = json.loads((SEED_DIR / "pharmacies.json").read_text(encoding="utf-8"))
    assert doc["meta"]["licence"] == "ODbL 1.0"
    assert "OpenStreetMap contributors" in doc["meta"]["source"]
    for row in doc["records"]:
        assert row["source"] == "osm" and row["osm_id"]
        assert exclusion_reason({"name": row["name"]}) is None
        assert row["is_partner"] is False


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (_pharmacy(lat=23.81, lon=90.41), "outside the Sylhet city area"),  # Dhaka
        (_pharmacy(osm_id=None), "needs osm_type and osm_id"),
        (
            _pharmacy(source="survey", osm_type=None, osm_id=None),
            "needs surveyed_by and surveyed_on",
        ),
        (_pharmacy(partner_since="2026-11-01"), "partner_since is set but is_partner is false"),
        (_pharmacy(phone="call me"), "phone"),
        (_pharmacy(stock=["Napa"]), "stock"),  # no field for what a shop has
    ],
)
def test_bad_pharmacy_rows_are_reported(data_dir: Path, row: dict[str, Any], message: str) -> None:
    _set_pharmacies(data_dir, [row])
    errors = _errors(data_dir)
    assert errors and any(message in e for e in errors), errors
    assert all(e.startswith("pharmacies.json[0] 'Test Pharmacy'") for e in errors)


def test_duplicate_osm_id_is_reported(data_dir: Path) -> None:
    _set_pharmacies(data_dir, [_pharmacy(), _pharmacy(name="Other", lat=24.90)])
    assert any("duplicate OpenStreetMap id node/9000000001" in e for e in _errors(data_dir))


def test_same_name_within_20_metres_is_a_duplicate(data_dir: Path) -> None:
    near = _pharmacy(name="test  PHARMACY", osm_id=2, lat=ZINDABAZAR[0] + 0.0001)  # about 11 m
    far = _pharmacy(osm_id=3, lat=ZINDABAZAR[0] + 0.001)  # about 111 m: a second branch
    _set_pharmacies(data_dir, [_pharmacy(), near, far])
    errors = _errors(data_dir)
    assert len(errors) == 1, errors
    assert errors[0].startswith("pharmacies.json[1]") and "11 m away" in errors[0]


def test_area_names_must_be_unique(data_dir: Path) -> None:
    path = data_dir / "sylhet_areas.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["records"].append(dict(doc["records"][0]))
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert any(
        e.startswith("sylhet_areas.json") and "duplicate name" in e for e in _errors(data_dir)
    )


def test_distance_metres() -> None:
    assert distance_metres(*ZINDABAZAR, *ZINDABAZAR) == 0
    # One thousandth of a degree of latitude is about 111 m.
    assert distance_metres(24.0, 91.0, 24.001, 91.0) == pytest.approx(111.2, abs=0.5)


# ---------------------------------------------------------------- phone numbers


def test_only_phones_allowed_to_be_shown_are_stored(data_dir: Path, engine: Engine) -> None:
    survey = {
        "source": "survey",
        "osm_type": None,
        "osm_id": None,
        "surveyed_by": "Team",
        "surveyed_on": "2026-11-10",
    }
    rows = [
        _pharmacy(name="OSM shop", phone="+880 1711-000001", osm_id=1),
        _pharmacy(
            name="OSM shop, owner asked to hide",
            phone="+880 1711-000002",
            osm_id=2,
            hide_phone=True,
        ),
        _pharmacy(name="Surveyed shop", phone="01711000003", lat=24.90, **survey),
        _pharmacy(
            name="Partner",
            phone="01711000004",
            lat=24.91,
            is_partner=True,
            partner_since="2026-11-01",
            **survey,
        ),
    ]
    _set_pharmacies(data_dir, rows)
    result = run_import(data_dir, engine)
    assert result.ok, result.errors
    with Session(engine) as session:
        phones = dict(session.execute(select(Pharmacy.name, Pharmacy.phone)).all())
    assert phones == {
        "OSM shop": "+880 1711-000001",
        "OSM shop, owner asked to hide": None,
        "Surveyed shop": None,  # survey numbers only for partners who agreed
        "Partner": "01711000004",
    }


# ---------------------------------------------------------------- fetch script rules


@pytest.mark.parametrize(
    "tags",
    [
        {"name": "Ahnaf Homeo & Herbal"},
        {"name": "Sylhet HOMEOPATHIC Hall"},
        {"name": "Hamdard Unani Dawakhana"},
        {"name": "Green Ayurvedic Store"},
        {"name": "মা হোমিও হল"},
        {"name": "Shifa", "healthcare:speciality": "homeopathy"},
        {"name": "Shifa", "homeopathy": "yes"},
        {},
    ],
)
def test_non_pharmacy_shops_are_excluded_by_rule(tags: dict[str, str]) -> None:
    assert exclusion_reason(tags) is not None


def test_fetch_keeps_hand_fields_and_reports_exclusions() -> None:
    elements = [
        {
            "type": "node",
            "id": 1,
            "lat": 24.9,
            "lon": 91.87,
            "tags": {"amenity": "pharmacy", "name": "Lazz  Pharma"},
        },
        {
            "type": "node",
            "id": 2,
            "lat": 24.9,
            "lon": 91.87,
            "tags": {"amenity": "pharmacy", "name": "Homeo Hall"},
        },
        {
            "type": "node",
            "id": 3,
            "lat": 24.9,
            "lon": 91.87,
            "tags": {"shop": "chemist", "name": "Chemist"},
        },
    ]
    previous = [
        {
            "osm_type": "node",
            "osm_id": 1,
            "is_partner": True,
            "partner_since": "2026-11-01",
            "hide_phone": True,
        }
    ]
    kept, excluded, counts = build_pharmacies(elements, previous)
    assert [r["name"] for r in kept] == ["Lazz Pharma"]
    assert kept[0]["is_partner"] is True and kept[0]["hide_phone"] is True
    assert excluded == [{"osm": "node/2", "name": "Homeo Hall", "reason": excluded[0]["reason"]}]
    assert counts["shop=chemist (not included)"] == 1
    assert keep_hand_fields([], previous) == []


# ---------------------------------------------------------------- API


def test_api_returns_the_whole_list(client: TestClient) -> None:
    r = client.get("/api/pharmacies", params={"city": "sylhet"})
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    seed = json.loads((SEED_DIR / "pharmacies.json").read_text(encoding="utf-8"))["records"]
    areas = json.loads((SEED_DIR / "sylhet_areas.json").read_text(encoding="utf-8"))["records"]
    assert data["city"] == "sylhet"
    assert tuple(data["bbox"]) == SYLHET_BBOX
    assert len(data["pharmacies"]) == len(seed)
    assert len(data["areas"]) == len(areas)
    first = data["pharmacies"][0]
    assert set(first) == {
        "id",
        "name",
        "name_bn",
        "lat",
        "lon",
        "address",
        "phone",
        "phone_from_osm",
        "is_partner",
    }
    assert set(data["areas"][0]) == {"id", "name", "name_bn", "lat", "lon"}
    for p in data["pharmacies"]:
        assert p["phone_from_osm"] == (p["phone"] is not None)


def test_api_defaults_to_sylhet_and_rejects_other_cities(client: TestClient) -> None:
    assert client.get("/api/pharmacies").status_code == 200
    r = client.get("/api/pharmacies", params={"city": "dhaka"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_api_takes_no_location(client: TestClient) -> None:
    """Distances are computed in the browser; the endpoint has no way to receive a position."""
    from app.main import app

    params = app.openapi()["paths"]["/api/pharmacies"]["get"].get("parameters", [])
    assert [p["name"] for p in params] == ["city"]


def test_api_is_rate_limited(client: TestClient) -> None:
    headers = {"X-Forwarded-For": "203.0.113.44"}
    for _ in range(get_settings().search_limit_per_minute):
        assert client.get("/api/pharmacies", headers=headers).status_code == 200
    blocked = client.get("/api/pharmacies", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
