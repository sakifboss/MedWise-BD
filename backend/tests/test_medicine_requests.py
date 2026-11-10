"""'Request this medicine': what is stored, who may call it, limits, and surviving the import."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.api import medicine_requests
from app.core.config import get_settings
from app.core.db import Base, make_engine
from app.models import MedicineRequest
from scripts.import_data import run_import

SECRET = "request-test-secret"


@pytest.fixture
def locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)


def _post(client: TestClient, body: dict, **headers: str):
    named = {
        k.replace("_", "-"): v for k, v in headers.items()
    }  # X_Forwarded_For -> X-Forwarded-For
    return client.post("/api/requests", json=body, headers={"X-MedWise-Frontend": SECRET, **named})


def _rows(engine: Engine) -> list[MedicineRequest]:
    with Session(engine) as session:
        return list(session.scalars(select(MedicineRequest).order_by(MedicineRequest.id)))


@pytest.fixture
def clean_requests(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session, session.begin():
        session.query(MedicineRequest).delete()


def test_stores_only_query_source_and_day(
    client: TestClient, seeded_engine: Engine, clean_requests: None, locked: None
) -> None:
    r = _post(client, {"query": "  Fexo   120 ", "source": "search"}, User_Agent="Phone/1.0")
    assert r.status_code == 201
    assert r.json() == {"data": {"saved": True}, "error": None}
    [row] = _rows(seeded_engine)
    assert (row.query, row.source) == ("Fexo 120", "search")
    assert row.requested_on == datetime.now(UTC).date()
    # The table has no column for anything else (IP, user agent, cookie, user id).
    columns = {c["name"] for c in inspect(seeded_engine).get_columns("medicine_requests")}
    assert columns == {"id", "query", "source", "requested_on"}


def test_long_queries_are_cut_to_80_characters(
    client: TestClient, seeded_engine: Engine, clean_requests: None, locked: None
) -> None:
    assert _post(client, {"query": "x" * 300, "source": "prescription"}).status_code == 201
    assert len(_rows(seeded_engine)[0].query) == 80


@pytest.mark.parametrize(
    "body",
    [
        {"query": "   ", "source": "search"},
        {"query": "", "source": "search"},
        {"query": "Fexo", "source": "email"},
        {"query": "Fexo"},
        {"query": "Fexo", "source": "search", "phone": "01700000000"},  # extra fields refused
        {"query": "x" * 501, "source": "search"},
    ],
)
def test_bad_requests_are_refused(client: TestClient, locked: None, body: dict) -> None:
    r = _post(client, body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_only_our_frontend_may_send_requests(client: TestClient, locked: None) -> None:
    r = client.post("/api/requests", json={"query": "Fexo", "source": "search"})
    assert r.status_code == 403


def test_per_client_limit(client: TestClient, clean_requests: None, locked: None) -> None:
    body = {"query": "Fexo", "source": "search"}
    for _ in range(get_settings().request_limit_per_hour):
        assert _post(client, body, X_Forwarded_For="203.0.113.5").status_code == 201
    blocked = _post(client, body, X_Forwarded_For="203.0.113.5")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert _post(client, body, X_Forwarded_For="198.51.100.7").status_code == 201


def test_daily_cap_for_everyone(
    client: TestClient, clean_requests: None, locked: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(medicine_requests.global_limiter, "limit", 2)
    body = {"query": "Fexo", "source": "search"}
    assert _post(client, body, X_Forwarded_For="203.0.113.1").status_code == 201
    assert _post(client, body, X_Forwarded_For="203.0.113.2").status_code == 201
    assert _post(client, body, X_Forwarded_For="203.0.113.3").status_code == 429


def test_requests_survive_the_seed_import(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    seed = get_settings().seed_dir
    assert run_import(seed, engine).ok
    with Session(engine) as session, session.begin():
        session.add(
            MedicineRequest(
                query="Fexo", source="search", requested_on=datetime(2026, 11, 10).date()
            )
        )
    assert run_import(seed, engine).ok  # drops and recreates every seed table ...
    assert [(r.query, r.source) for r in _rows(engine)] == [("Fexo", "search")]  # ... not this one
    engine.dispose()


def test_seed_metadata_does_not_include_the_request_log() -> None:
    assert "medicine_requests" not in Base.metadata.tables


def test_stats_counts_come_from_the_data(client: TestClient) -> None:
    seed = get_settings().seed_dir
    counts = {
        name: len(json.loads((seed / f"{name}.json").read_text(encoding="utf-8"))["records"])
        for name in ("generics", "brands", "manufacturers", "interactions")
    }
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["data"] == counts


def test_top_requests_groups_case_and_spaces() -> None:
    from scripts.top_requests import group_requests

    d1, d2 = datetime(2026, 11, 1).date(), datetime(2026, 11, 9).date()
    rows = [
        ("Fexo", "search", d1),
        ("fexo ", "prescription", d2),
        ("Fexo", "search", d1),
        ("Napa Extend", "search", d1),
    ]
    top = group_requests(rows, limit=30)
    assert [(t.query, t.count) for t in top] == [("Fexo", 3), ("Napa Extend", 1)]
    assert top[0].sources == {"search": 2, "prescription": 1}
    assert top[0].last_requested == d2
    assert len(group_requests(rows, limit=1)) == 1


def test_top_requests_script_reads_a_database(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from scripts.top_requests import main

    url = f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}"
    engine = make_engine(url)
    assert run_import(get_settings().seed_dir, engine).ok
    with Session(engine) as session, session.begin():
        session.add_all(
            MedicineRequest(query=q, source="search", requested_on=datetime(2026, 11, 10).date())
            for q in ("Fexo", "FEXO", "Viodin")
        )
    engine.dispose()
    assert main(["--database-url", url]) == 0
    out = capsys.readouterr().out
    assert "3 requests in total" in out
    assert "Fexo  (search 2)" in out
