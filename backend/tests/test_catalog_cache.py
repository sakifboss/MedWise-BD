"""The in-memory catalog cache: answers repeat without a database trip, and stay correct."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event

from app.core import catalog_cache as cache_module
from app.core.catalog_cache import CatalogCache, catalog_cache
from app.core.config import get_settings
from scripts.import_data import run_import


@contextmanager
def count_queries(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


# ---------------------------------------------------------------- the cache itself


def test_builds_once_per_key() -> None:
    cache = CatalogCache()
    calls: list[str] = []

    def build(name: str) -> str:
        calls.append(name)
        return name.upper()

    assert cache.get_or_build(("a",), lambda: build("a")) == "A"
    assert cache.get_or_build(("a",), lambda: build("a")) == "A"
    assert cache.get_or_build(("b",), lambda: build("b")) == "B"
    assert calls == ["a", "b"]


def test_errors_are_not_cached() -> None:
    cache = CatalogCache()

    def fail() -> str:
        raise LookupError("not found")

    with pytest.raises(LookupError):
        cache.get_or_build(("x",), fail)
    assert len(cache) == 0
    assert cache.get_or_build(("x",), lambda: "found") == "found"


def test_entries_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(get_settings(), "catalog_cache_seconds", 60)
    cache = CatalogCache()
    cache.get_or_build(("k",), lambda: 1)
    now[0] += 59
    assert cache.get_or_build(("k",), lambda: 2) == 1
    now[0] += 2
    assert cache.get_or_build(("k",), lambda: 3) == 3


def test_zero_seconds_turns_it_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "catalog_cache_seconds", 0)
    cache = CatalogCache()
    assert [cache.get_or_build(("k",), lambda n=n: n) for n in range(3)] == [0, 1, 2]
    assert len(cache) == 0


def test_least_recently_used_goes_first() -> None:
    cache = CatalogCache(max_entries=2)
    cache.get_or_build("a", lambda: 1)
    cache.get_or_build("b", lambda: 2)
    cache.get_or_build("a", lambda: 0)  # a is now the most recent
    cache.get_or_build("c", lambda: 3)  # b goes
    assert cache.get_or_build("a", lambda: -1) == 1
    assert cache.get_or_build("b", lambda: -2) == -2


# ---------------------------------------------------------------- the API


CATALOG_GETS = [
    "/api/alternatives/BR00001?lang=en",
    "/api/alternatives/BR00001?lang=bn",
    "/api/generics",
    "/api/generics/1?lang=bn",
    "/api/generics/1/ranking?strength=500%20mg&dosage_form=tablet&lang=en",
    "/api/brands/index",
    "/api/stats",
    "/api/manufacturers",
    "/api/manufacturers/1",
    "/api/pharmacies?city=sylhet",
    "/api/symptom-guide/setup?lang=bn",
    "/api/search?q=napa",
    "/api/search?q=%E0%A6%A8%E0%A6%BE%E0%A6%AA%E0%A6%BE",  # Bangla "napa"
]


@pytest.mark.parametrize("path", CATALOG_GETS)
def test_repeat_answers_need_no_database(
    client: TestClient, seeded_engine: Engine, path: str
) -> None:
    first = client.get(path)
    assert first.status_code == 200, first.text
    with count_queries(seeded_engine) as queries:
        second = client.get(path)
    assert second.json() == first.json()
    assert queries == []


def test_search_reads_names_once_for_any_query(client: TestClient, seeded_engine: Engine) -> None:
    client.get("/api/search?q=napa")
    with count_queries(seeded_engine) as queries:
        hits = client.get("/api/search?q=seclo").json()["data"]["results"]
    assert queries == []
    assert hits[0]["name"] == "Seclo"


def test_interaction_check_repeats_without_database(
    client: TestClient, seeded_engine: Engine
) -> None:
    body = {"generic_ids": [1, 2, 3]}
    first = client.post("/api/interactions/check", json=body)
    assert first.status_code == 200, first.text
    with count_queries(seeded_engine) as queries:
        second = client.post("/api/interactions/check", json=body)
    assert (queries, second.json()) == ([], first.json())


def test_generics_list_is_two_queries(client: TestClient, seeded_engine: Engine) -> None:
    """One for the names and one for every presentation (it was one query per generic)."""
    with count_queries(seeded_engine) as queries:
        data = client.get("/api/generics").json()["data"]
    assert len(queries) == 2
    # Same groups, in the same order, as each generic's own page.
    for item in data:
        page = client.get(f"/api/generics/{item['id']}").json()["data"]
        assert item["presentations"] == page["presentations"], item["name"]
    assert sum(bool(item["presentations"]) for item in data) >= len(data) - 1  # Warfarin: none


def test_not_found_is_not_cached(client: TestClient) -> None:
    assert client.get("/api/alternatives/BR99999").status_code == 404
    assert len(catalog_cache) == 0


def test_old_id_and_code_share_nothing_wrong(client: TestClient) -> None:
    """An old id link and lower-case codes still give the right brand."""
    by_code = client.get("/api/alternatives/BR00001").json()["data"]
    lower = client.get("/api/alternatives/br00001").json()["data"]
    assert lower == by_code
    by_id = client.get(f"/api/alternatives/{by_code['selected_brand_id']}").json()["data"]
    assert by_id["selected_brand_code"] == "BR00001"


def test_import_clears_the_cache(client: TestClient, seeded_engine: Engine) -> None:
    client.get("/api/stats")
    assert len(catalog_cache) > 0
    result = run_import(get_settings().seed_dir, seeded_engine)
    assert result.ok, result.errors
    assert len(catalog_cache) == 0
