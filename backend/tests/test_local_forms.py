"""Interactions are not shown for generics the catalog lists only in local forms (eye drops, ...),
and brand aliases from the seed data are matched by search and the prescription scanner."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.services.local_forms import local_only_forms
from app.services.ocr import ExtractedMedicine
from app.services.prescription import match_medicine

ROUTES = {"tablet": "systemic", "eye drops": "local", "cream": "local"}


def test_only_generics_with_every_form_local() -> None:
    brands = [
        ("Chloramphenicol", "eye drops"),
        ("Chloramphenicol", "eye drops"),
        ("Fusidic acid", "cream"),
        ("Fusidic acid", "eye drops"),
        ("Paracetamol", "tablet"),
        ("Azithromycin", "tablet"),
        ("Azithromycin", "eye drops"),  # one form taken by mouth: interactions shown
        ("Unknown", "patch"),  # a form without a route counts as systemic
    ]
    assert local_only_forms(brands, ROUTES) == {
        "Chloramphenicol": ["eye drops"],
        "Fusidic acid": ["cream", "eye drops"],
    }


def _generic_id(client: TestClient, name: str) -> int:
    generics = client.get("/api/generics").json()["data"]
    return next(g["id"] for g in generics if g["name"] == name)


def test_generic_page_says_why_interactions_are_not_shown(client: TestClient) -> None:
    chloramphenicol = client.get(f"/api/generics/{_generic_id(client, 'Chloramphenicol')}").json()
    assert chloramphenicol["data"]["interactions"] == []
    assert chloramphenicol["data"]["interactions_not_shown_forms"] == ["eye drops"]
    warfarin = client.get(f"/api/generics/{_generic_id(client, 'Warfarin')}").json()["data"]
    assert warfarin["interactions"] and warfarin["interactions_not_shown_forms"] == []


def test_checker_reports_local_only_generics_and_counts_only_checkable_pairs(
    client: TestClient,
) -> None:
    ids = [_generic_id(client, n) for n in ("Chloramphenicol", "Warfarin", "Aspirin")]
    data = client.post("/api/interactions/check", json={"generic_ids": ids}).json()["data"]
    assert data["not_shown"] == [
        {"generic_id": ids[0], "generic_name": "Chloramphenicol", "forms": ["eye drops"]}
    ]
    assert data["pairs_checked"] == 1  # Warfarin + Aspirin only
    assert all(
        "Chloramphenicol" not in (i["generic_a"]["name"], i["generic_b"]["name"])
        for i in data["interactions"]
    )
    alone = client.post("/api/interactions/check", json={"generic_ids": ids[:2]}).json()["data"]
    assert alone["pairs_checked"] == 0 and alone["interactions"] == []


def test_search_and_scanner_find_a_brand_by_its_alias(
    client: TestClient, seeded_engine: Engine
) -> None:
    hits = client.get("/api/search", params={"q": "Mycetin"}).json()["data"]["results"]
    assert hits[0]["type"] == "brand" and hits[0]["name"] == "SQ-Mycetin"
    with Session(seeded_engine) as db:
        match = match_medicine(db, ExtractedMedicine("Mycedin", None))  # as written on rx04
    top = match.options[match.suggested_index or 0]
    assert match.suggested_index is not None
    assert (top.name, top.generic_name) == ("SQ-Mycetin", "Chloramphenicol")
