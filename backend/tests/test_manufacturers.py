"""API tests for the manufacturer transparency endpoints."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def _ok(response: Any) -> Any:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["error"] is None
    return body["data"]


@pytest.fixture
def listing(client: TestClient) -> list[dict]:
    return _ok(client.get("/api/manufacturers"))


def test_list_is_ranked_by_quality(listing: list[dict]) -> None:
    assert len(listing) == 14
    scores = [m["quality_score"] for m in listing]
    assert scores == sorted(scores, reverse=True)
    assert [m["quality_rank"] for m in listing] == list(range(1, len(listing) + 1))
    brands = json.loads((get_settings().seed_dir / "brands.json").read_text(encoding="utf-8"))
    assert sum(m["brand_count"] for m in listing) == len(brands["records"])  # every brand counted


def test_detail_points_add_up_to_the_quality_score(client: TestClient, listing: list[dict]) -> None:
    for item in listing:
        detail = _ok(client.get(f"/api/manufacturers/{item['id']}"))
        assert detail["quality_score"] == item["quality_score"]
        assert sum(f["points"] for f in detail["factors"]) == pytest.approx(
            detail["quality_score"], abs=0.3
        )
        assert sum(f["weight"] for f in detail["factors"]) == pytest.approx(1.0)
        assert len(detail["brands"]) == item["brand_count"]


def test_detail_matches_the_quality_used_in_rankings(client: TestClient) -> None:
    napa = next(
        r
        for r in _ok(client.get("/api/search", params={"q": "Napa"}))["results"]
        if r["strength"] == "500 mg"
    )
    ranked = _ok(client.get(f"/api/alternatives/{napa['id']}"))["alternatives"]
    for alt in ranked:
        detail = _ok(client.get(f"/api/manufacturers/{alt['manufacturer']['id']}"))
        assert detail["quality_score"] == pytest.approx(100 * alt["quality_score"], abs=0.1)


def test_detail_explains_approvals_and_unknowns(client: TestClient, listing: list[dict]) -> None:
    square = next(m for m in listing if m["name"] == "Square Pharmaceuticals PLC")
    detail = _ok(client.get(f"/api/manufacturers/{square['id']}"))
    assert detail["stringent_approvals"] == ["US FDA", "UK MHRA", "EU GMP", "TGA Australia"]
    assert detail["approvals_missing"] == []
    assert "recall_history" in detail["unknowns"]
    assert all(url.startswith("https://") for url in detail["source_urls"])
    assert {b["generic_name"] for b in detail["brands"]} >= {"Paracetamol", "Omeprazole"}

    acme = next(m for m in listing if m["name"] == "The ACME Laboratories Ltd")
    acme_detail = _ok(client.get(f"/api/manufacturers/{acme['id']}"))
    assert acme_detail["export_country_count"] is None
    assert "export_country_count" in acme_detail["unknowns"]
    assert "US FDA" in acme_detail["approvals_missing"]


def test_recall_is_scored_equally_when_nobody_has_recall_data(
    client: TestClient, listing: list[dict]
) -> None:
    recall_scores = {
        next(
            f["score"]
            for f in _ok(client.get(f"/api/manufacturers/{m['id']}"))["factors"]
            if f["key"] == "recall_history"
        )
        for m in listing
    }
    assert len(recall_scores) == 1  # so it cannot change any ranking


def test_unknown_manufacturer(client: TestClient) -> None:
    response = client.get("/api/manufacturers/99999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
