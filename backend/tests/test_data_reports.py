"""'Report a problem': what is stored, who may call it, limits, surviving the import, read-out."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import make_engine
from app.models import Brand, DataReport, Manufacturer
from scripts.import_data import run_import
from scripts.top_reports import group_reports, main

SECRET = "report-test-secret"


@pytest.fixture
def locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)


@pytest.fixture
def clean(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session, session.begin():
        session.query(DataReport).delete()


def _post(client: TestClient, body: dict, **headers: str):
    named = {k.replace("_", "-"): v for k, v in headers.items()}
    return client.post("/api/reports", json=body, headers={"X-MedWise-Frontend": SECRET, **named})


def _seclo(engine: Engine) -> tuple[int, str]:
    with Session(engine) as session:
        brand_id, maker = session.execute(
            select(Brand.id, Manufacturer.name)
            .join(Manufacturer, Brand.manufacturer_id == Manufacturer.id)
            .where(Brand.name == "Seclo")
        ).one()
    return brand_id, maker


def _rows(engine: Engine) -> list[DataReport]:
    with Session(engine) as session:
        return list(session.scalars(select(DataReport).order_by(DataReport.id)))


def test_stores_only_the_brand_reason_and_day(
    client: TestClient, seeded_engine: Engine, clean: None, locked: None
) -> None:
    brand_id, maker = _seclo(seeded_engine)
    r = _post(client, {"brand_id": brand_id, "reason": "wrong_price"}, User_Agent="Phone/1.0")
    assert r.status_code == 201
    assert r.json() == {"data": {"saved": True}, "error": None}
    [row] = _rows(seeded_engine)
    assert (row.brand_id, row.brand_name, row.manufacturer, row.reason) == (
        brand_id,
        "Seclo",
        maker,
        "wrong_price",
    )
    assert (row.strength, row.dosage_form) == ("20 mg", "capsule")
    assert row.brand_code is not None and row.brand_code.startswith("BR")
    assert row.reported_on == datetime.now(UTC).date()
    # No column for anything about the person (IP, user agent, cookie, user id, free text).
    columns = {c["name"] for c in inspect(seeded_engine).get_columns("data_reports")}
    assert columns == {
        "id",
        "brand_id",
        "brand_code",
        "brand_name",
        "manufacturer",
        "strength",
        "dosage_form",
        "reason",
        "reported_on",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"brand_id": 1, "reason": "too expensive"},  # only the fixed reasons
        {"brand_id": 1, "reason": "other", "note": "the shop said..."},  # no free text
        {"brand_id": 0, "reason": "other"},
        {"reason": "other"},
    ],
)
def test_rejects_anything_else(
    client: TestClient, seeded_engine: Engine, clean: None, locked: None, body: dict
) -> None:
    assert _post(client, body).status_code == 422
    assert _rows(seeded_engine) == []


def test_unknown_brand(
    client: TestClient, seeded_engine: Engine, clean: None, locked: None
) -> None:
    r = _post(client, {"brand_id": 999999, "reason": "not_sold"})
    assert r.status_code == 404
    assert _rows(seeded_engine) == []


def test_only_our_frontend_may_report(
    client: TestClient, seeded_engine: Engine, clean: None, locked: None
) -> None:
    brand_id, _ = _seclo(seeded_engine)
    r = client.post("/api/reports", json={"brand_id": brand_id, "reason": "other"})
    assert r.status_code == 403
    assert _rows(seeded_engine) == []


def test_limits_per_client_and_per_day(
    client: TestClient,
    seeded_engine: Engine,
    clean: None,
    locked: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import data_reports

    brand_id, _ = _seclo(seeded_engine)
    body = {"brand_id": brand_id, "reason": "other"}
    for _ in range(get_settings().report_limit_per_hour):
        assert _post(client, body, X_Forwarded_For="203.0.113.80").status_code == 201
    assert _post(client, body, X_Forwarded_For="203.0.113.80").status_code == 429
    assert _post(client, body, X_Forwarded_For="203.0.113.81").status_code == 201  # someone else
    monkeypatch.setattr(data_reports.global_limiter, "allow", lambda key: False)  # day is full
    assert _post(client, body, X_Forwarded_For="203.0.113.82").status_code == 429


def test_reports_survive_the_seed_import(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    assert run_import(get_settings().seed_dir, engine).ok
    with Session(engine) as session, session.begin():
        session.add(
            DataReport(
                brand_id=1,
                brand_name="Seclo",
                manufacturer="Square Pharmaceuticals PLC",
                strength="20 mg",
                dosage_form="capsule",
                reason="wrong_price",
                reported_on=date(2026, 11, 11),
            )
        )
    assert run_import(get_settings().seed_dir, engine).ok  # drops and rebuilds the seed tables
    assert [r.brand_name for r in _rows(engine)] == ["Seclo"]
    engine.dispose()


def test_top_reports_groups_by_brand_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = [
        ("Seclo", "Square", "20 mg", "capsule", "wrong_price", date(2026, 11, 10)),
        ("Seclo", "Square", "20 mg", "capsule", "wrong_price", date(2026, 11, 11)),
        ("Seclo", "Square", "20 mg", "capsule", "not_sold", date(2026, 11, 9)),
        ("Napa", "Beximco", "500 mg", "tablet", "other", date(2026, 11, 11)),
    ]
    top = group_reports(rows, 10)
    assert [(t.brand, t.count) for t in top] == [
        ("Seclo 20 mg capsule (Square)", 3),
        ("Napa 500 mg tablet (Beximco)", 1),
    ]
    assert top[0].reasons == {"wrong_price": 2, "not_sold": 1}
    assert top[0].last_reported == date(2026, 11, 11)
    # The script itself on an empty database.
    url = f"sqlite:///{(tmp_path / 'empty.sqlite').as_posix()}"
    assert main(["--database-url", url]) == 0
    assert "No reports yet" in capsys.readouterr().out
