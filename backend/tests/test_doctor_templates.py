# ruff: noqa: F811  (fixtures shared with test_doctor_accounts)
"""R5: doctor templates and favourite tests. Only each doctor's own, never patient fields; the
rx-pad request log keeps only the name, the source and the day."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.api import doctor_templates as templates_api
from app.core.config import get_settings
from app.core.db import make_engine
from app.main import app
from app.models import DoctorTemplate, MedicineRequest
from scripts import doctors as admin
from scripts.import_data import run_import
from tests.test_doctor_accounts import SITE, api, signup  # noqa: F401


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """Doctor tables plus the medicine catalog (templates check brand codes against it)."""
    db = make_engine(f"sqlite:///{(tmp_path / 'templates.sqlite').as_posix()}")
    assert run_import(get_settings().seed_dir, db).ok
    yield db
    db.dispose()


NAPA = {
    "kind": "brand",
    "code": "BR00001",
    "name": "Napa 500 mg tablet",
    "pattern": "1+0+1",
    "unit": "tablet",
    "food": "after",
    "duration": "5d",
    "substitution": True,
    "note": "if fever is over 101°F",
}
GENERIC = {
    "kind": "generic",
    "name": "Metformin 500 mg tablet",
    "generic": "Metformin",
    "strength": "500 mg",
    "dosage_form": "tablet",
    "pattern": "1+0+1",
    "duration": "c",
}
FREE = {"kind": "free", "name": "Ambrox syrup", "unit": "spoon", "pattern": "2+2+2"}
BODY = {"name": "Fever (adult)", "lines": [NAPA, GENERIC, FREE], "tests": "CBC", "advice": "Rest"}


def create(api: TestClient, **change):  # noqa: ANN003, ANN201
    return api.post("/api/doctor/templates", json={**BODY, **change})


def test_create_list_get_update_rename_delete(api: TestClient) -> None:
    signup(api)
    r = create(api)
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store"
    t = r.json()["data"]
    assert [line["kind"] for line in t["lines"]] == ["brand", "generic", "free"]
    assert t["lines"][0]["note"] == "if fever is over 101°F" and not t["lines"][0]["gone"]
    listed = api.get("/api/doctor/templates").json()["data"]
    assert [(x["name"], x["line_count"]) for x in listed] == [("Fever (adult)", 3)]
    got = api.get(f"/api/doctor/templates/{t['id']}").json()["data"]
    assert got["tests"] == "CBC" and got["advice"] == "Rest"
    updated = api.post(
        f"/api/doctor/templates/{t['id']}", json={**BODY, "lines": [NAPA], "advice": ""}
    )
    assert len(updated.json()["data"]["lines"]) == 1 and updated.json()["data"]["advice"] == ""
    renamed = api.post(f"/api/doctor/templates/{t['id']}/rename", json={"name": "  Fever  child "})
    assert renamed.json()["data"]["name"] == "Fever child"
    assert api.post(f"/api/doctor/templates/{t['id']}/delete").status_code == 200
    assert api.get("/api/doctor/templates").json()["data"] == []


def test_names_are_unique_per_doctor_ignoring_case(api: TestClient) -> None:
    signup(api)
    create(api)
    again = create(api, name="FEVER (ADULT)")
    assert again.status_code == 409 and again.json()["error"]["code"] == "template_name_taken"
    other = create(api, name="Cough").json()["data"]
    taken = api.post(f"/api/doctor/templates/{other['id']}/rename", json={"name": "fever (adult)"})
    assert taken.status_code == 409


def test_a_doctor_never_sees_another_doctors_templates(api: TestClient) -> None:
    signup(api)
    mine = create(api).json()["data"]["id"]
    other = TestClient(app, base_url="https://testserver", headers=dict(api.headers))
    signup(other, email="other@example.com")
    assert other.get("/api/doctor/templates").json()["data"] == []
    for call in (
        lambda: other.get(f"/api/doctor/templates/{mine}"),
        lambda: other.post(f"/api/doctor/templates/{mine}", json=BODY),
        lambda: other.post(f"/api/doctor/templates/{mine}/rename", json={"name": "x"}),
        lambda: other.post(f"/api/doctor/templates/{mine}/delete"),
    ):
        assert call().status_code == 404
    assert api.get(f"/api/doctor/templates/{mine}").status_code == 200  # still there


def test_limits_and_validation(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    signup(api)
    assert create(api, lines=[NAPA] * 13).status_code == 422
    assert create(api, name="").status_code == 422
    assert create(api, name="x" * 61).status_code == 422
    assert create(api, lines=[{**NAPA, "duration": "400d"}]).status_code == 422
    assert create(api, lines=[{**NAPA, "patient": "Rahim"}]).status_code == 422  # no other fields
    assert create(api, patient_name="Rahim").status_code == 422
    monkeypatch.setattr(templates_api, "MAX_TEMPLATES", 2)
    assert create(api, name="a").status_code == 201
    assert create(api, name="b").status_code == 201
    full = create(api, name="c")
    assert full.status_code == 409 and full.json()["error"]["code"] == "template_limit"


def test_a_brand_that_left_the_catalog_becomes_a_free_line(api: TestClient) -> None:
    signup(api)
    gone = {**NAPA, "code": "BR99999", "name": "Oldbrand 10 mg tablet"}
    t = create(api, lines=[gone, NAPA]).json()["data"]
    assert t["lines"][0] | {} == {
        **t["lines"][0],
        "kind": "free",
        "code": None,
        "gone": True,
        "name": "Oldbrand 10 mg tablet",
    }
    assert t["lines"][1]["kind"] == "brand" and not t["lines"][1]["gone"]


def test_favourite_tests(api: TestClient) -> None:
    signup(api)
    assert api.get("/api/doctor/favourite-tests").json()["data"] == {"tests": []}
    saved = api.post(
        "/api/doctor/favourite-tests", json={"tests": ["CBC", " cbc ", "Urine  R/E", "", "RBS"]}
    )
    assert saved.json()["data"]["tests"] == ["CBC", "Urine R/E", "RBS"]
    assert api.post("/api/doctor/favourite-tests", json={"tests": ["x"] * 51}).status_code == 422
    assert api.post("/api/doctor/favourite-tests", json={"tests": ["x" * 81]}).status_code == 422
    assert api.get("/api/doctor/favourite-tests").json()["data"]["tests"] == [
        "CBC",
        "Urine R/E",
        "RBS",
    ]


def test_changes_need_our_origin(api: TestClient) -> None:
    signup(api)
    r = api.post("/api/doctor/templates", json=BODY, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert api.get("/api/doctor/templates", headers={"X-MedWise-Frontend": "no"}).status_code == 403


def test_export_and_account_deletion(api: TestClient, engine: Engine) -> None:  # noqa: F811
    signup(api)
    create(api)
    api.post("/api/doctor/favourite-tests", json={"tests": ["CBC"]})
    data = api.get("/api/doctor/export").json()["data"]
    assert data["favourite_tests"] == ["CBC"] and data["templates"][0]["name"] == "Fever (adult)"
    api.post("/api/doctor/delete", json={"password": "chamber-lamp-river-42"})
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DoctorTemplate)) == 0
    signup(api, email="again@example.com")
    create(api)
    with Session(engine) as db:
        admin.cmd_delete(db, "again@example.com", ask=lambda _p: "again@example.com")
        assert db.scalar(select(func.count()).select_from(DoctorTemplate)) == 0


def test_rx_pad_request_rows_hold_only_name_source_and_day(
    api: TestClient,
    engine: Engine,  # noqa: F811
) -> None:
    signup(api)  # a logged-in doctor: the session cookie is not sent to /api/requests anyway
    r = api.post("/api/requests", json={"query": "  Ambrox   syrup ", "source": "rx-pad"})
    assert r.status_code == 201
    with Session(engine) as db:
        rows = db.execute(select(MedicineRequest)).scalars().all()
    assert [(x.query, x.source) for x in rows] == [("Ambrox syrup", "rx-pad")]
    assert set(MedicineRequest.__table__.columns.keys()) == {
        "id",
        "query",
        "source",
        "requested_on",
    }


def test_nothing_is_logged(api: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    signup(api)
    create(api)
    assert "Fever (adult)" not in caplog.text and "101°F" not in caplog.text
