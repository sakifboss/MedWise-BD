import json
import re
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _ok(response: Any) -> Any:
    body = response.json()
    assert response.status_code == 200, body
    assert set(body) == {"data", "error"}
    assert body["error"] is None
    return body["data"]


def _err(response: Any, status: int, code: str) -> dict:
    body = response.json()
    assert response.status_code == status, body
    assert body["data"] is None
    assert body["error"]["code"] == code
    return body["error"]


def _brand_id(client: TestClient, name: str, strength: str) -> int:
    results = _ok(client.get("/api/search", params={"q": name}))["results"]
    return next(r["id"] for r in results if r["name"] == name and r["strength"] == strength)


# ---------------------------------------------------------------- health


def test_health(client: TestClient) -> None:
    assert _ok(client.get("/api/health")) == {
        "status": "ok",
        "database": "ok",
        "version": "dev",
        "frontend_secret": "not set",
    }


# ---------------------------------------------------------------- search


def test_search_brand_exact(client: TestClient) -> None:
    data = _ok(client.get("/api/search", params={"q": "Napa"}))
    top = data["results"][0]
    assert top["type"] == "brand"
    assert top["name"] == "Napa"
    assert top["generic_name"] == "Paracetamol"
    assert top["manufacturer"] == "Beximco Pharmaceuticals Ltd"
    # Both presentations of the brand are returned.
    strengths = {r["strength"] for r in data["results"] if r["name"] == "Napa"}
    assert strengths == {"500 mg", "120 mg/5 ml"}


def test_search_generic_ranks_first(client: TestClient) -> None:
    top = _ok(client.get("/api/search", params={"q": "paracetamol"}))["results"][0]
    assert top == {**top, "type": "generic", "name": "Paracetamol"}


def test_search_tolerates_typos(client: TestClient) -> None:
    results = _ok(client.get("/api/search", params={"q": "sefiksim"}))["results"]
    assert any(r["type"] == "generic" and r["name"] == "Cefixime" for r in results)


def test_search_bangla_input(client: TestClient) -> None:
    data = _ok(client.get("/api/search", params={"q": "সেফিক্সিম"}))
    assert data["interpreted_as"] == "sefiksim"
    assert data["results"][0]["name"] == "Cefixime"


def test_search_no_match(client: TestClient) -> None:
    assert _ok(client.get("/api/search", params={"q": "zzqqxx"}))["results"] == []


def test_search_respects_limit(client: TestClient) -> None:
    assert len(_ok(client.get("/api/search", params={"q": "a", "limit": 3}))["results"]) <= 3


def test_search_requires_query(client: TestClient) -> None:
    error = _err(client.get("/api/search"), 422, "validation_error")
    assert error["details"][0]["field"] == "query.q"


# ---------------------------------------------------------------- generic detail


def test_generic_detail(client: TestClient) -> None:
    generic_id = _ok(client.get("/api/search", params={"q": "Warfarin"}))["results"][0]["id"]
    data = _ok(client.get(f"/api/generics/{generic_id}"))
    assert data["name"] == "Warfarin"
    assert data["indications"]
    assert data["source_urls"] == ["https://www.nhs.uk/medicines/warfarin/"]
    # Warfarin 5 mg had one brand from our manufacturers, so the group was dropped (P7); the
    # generic page and its interactions stay.
    assert data["presentations"] == []
    severities = [i["severity"] for i in data["interactions"]]
    assert len(severities) >= 14
    assert severities == sorted(severities, key=["major", "moderate", "minor"].index)
    assert "Warfarin" not in {i["generic_name"] for i in data["interactions"]}


def test_generic_interactions_found_from_either_side(client: TestClient) -> None:
    generic_id = _ok(client.get("/api/search", params={"q": "Aspirin"}))["results"][0]["id"]
    names = {
        i["generic_name"] for i in _ok(client.get(f"/api/generics/{generic_id}"))["interactions"]
    }
    assert names == {
        "Amlodipine",
        "Bisoprolol",  # DDInter file C (cardiovascular), added in P7
        "Ciprofloxacin",
        "Clopidogrel",
        "Esomeprazole",
        "Ibuprofen",
        "Losartan",
        "Omeprazole",
        "Pantoprazole",
        "Warfarin",
    }


def test_generic_not_found(client: TestClient) -> None:
    _err(client.get("/api/generics/99999"), 404, "not_found")


def test_generic_bad_id(client: TestClient) -> None:
    _err(client.get("/api/generics/abc"), 422, "validation_error")


# ---------------------------------------------------------------- alternatives


def test_alternatives_same_generic_strength_and_form(client: TestClient) -> None:
    brand_id = _brand_id(client, "Napa", "500 mg")
    data = _ok(client.get(f"/api/alternatives/{brand_id}"))
    assert data["generic"]["name"] == "Paracetamol"
    assert (data["strength"], data["dosage_form"]) == ("500 mg", "tablet")
    names = {a["name"] for a in data["alternatives"]}
    assert names == {"Napa", "Ace", "Renova", "Reset", "Tamen", "Xpa", "Sinapol"}  # no suspensions


def test_alternatives_are_ranked_and_explained(client: TestClient) -> None:
    data = _ok(client.get(f"/api/alternatives/{_brand_id(client, 'Ace', '500 mg')}"))
    alternatives = data["alternatives"]
    assert [a["rank"] for a in alternatives] == list(range(1, len(alternatives) + 1))
    scores = [a["final_score"] for a in alternatives]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert all(a["reasons"] for a in alternatives)
    assert all(a["price_source_url"].startswith("https://") for a in alternatives)
    assert [a["name"] for a in alternatives if a["is_selected"]] == ["Ace"]
    assert data["disclaimer"] == "Consult your doctor or pharmacist before changing any medicine."


def test_alternatives_score_matches_formula(client: TestClient) -> None:
    data = _ok(client.get(f"/api/alternatives/{_brand_id(client, 'Napa', '500 mg')}"))
    for a in data["alternatives"]:
        b = a["quality_breakdown"]
        q = (
            0.30 * b["certification"]
            + 0.25 * b["export"]
            + 0.20 * b["compliance"]
            + 0.15 * (1 - b["recall_history"])
            + 0.10 * b["market"]
        )
        assert abs(q - a["quality_score"]) < 0.01
        assert (
            abs(100 * (0.8 * a["quality_score"] + 0.2 * a["price_score"]) - a["final_score"]) < 0.1
        )


def test_alternatives_not_found(client: TestClient) -> None:
    error = _err(client.get("/api/alternatives/99999"), 404, "not_found")
    assert "99999" in error["message"]


# ---------------------------------------------------------------- generic ranking


def _generic_id(client: TestClient, name: str) -> int:
    results = _ok(client.get("/api/search", params={"q": name}))["results"]
    return next(r["id"] for r in results if r["type"] == "generic" and r["name"] == name)


def test_generic_ranking_matches_brand_alternatives(client: TestClient) -> None:
    generic_id = _generic_id(client, "Paracetamol")
    params = {"strength": "500MG", "dosage_form": "Tablet"}  # normalised by the API
    data = _ok(client.get(f"/api/generics/{generic_id}/ranking", params=params))
    assert data["selected_brand_id"] is None
    assert (data["strength"], data["dosage_form"]) == ("500 mg", "tablet")
    assert not any(a["is_selected"] for a in data["alternatives"])

    via_brand = _ok(client.get(f"/api/alternatives/{_brand_id(client, 'Napa', '500 mg')}"))
    assert [a["brand_id"] for a in data["alternatives"]] == [
        a["brand_id"] for a in via_brand["alternatives"]
    ]


def test_generic_ranking_unknown_presentation(client: TestClient) -> None:
    generic_id = _generic_id(client, "Paracetamol")
    params = {"strength": "999 mg", "dosage_form": "tablet"}
    _err(client.get(f"/api/generics/{generic_id}/ranking", params=params), 404, "not_found")


def test_generic_ranking_requires_params(client: TestClient) -> None:
    _err(client.get("/api/generics/1/ranking"), 422, "validation_error")


# ---------------------------------------------------------------- language


def test_alternatives_in_bangla(client: TestClient) -> None:
    brand_id = _brand_id(client, "Napa", "500 mg")
    en = _ok(client.get(f"/api/alternatives/{brand_id}"))
    bn = _ok(client.get(f"/api/alternatives/{brand_id}", params={"lang": "bn"}))
    assert bn["disclaimer"] == "কোনো ওষুধ বদলানোর আগে আপনার ডাক্তার বা ফার্মাসিস্টের পরামর্শ নিন।"
    assert all("ইউনিট" in a["reasons"][-1] for a in bn["alternatives"])
    # Same ranking and scores in both languages; only the wording changes.
    assert [(a["name"], a["final_score"]) for a in en["alternatives"]] == [
        (a["name"], a["final_score"]) for a in bn["alternatives"]
    ]


def test_generic_interactions_in_bangla(client: TestClient) -> None:
    generic_id = _ok(client.get("/api/search", params={"q": "Warfarin"}))["results"][0]["id"]
    data = _ok(client.get(f"/api/generics/{generic_id}", params={"lang": "bn"}))
    assert all(i["description"].startswith("DDInter অনুযায়ী") for i in data["interactions"])


def test_unknown_language_is_rejected(client: TestClient) -> None:
    _err(client.get("/api/generics/1", params={"lang": "fr"}), 422, "validation_error")


def test_generic_text_falls_back_to_english_until_translated() -> None:
    from app.api.generics import _localized
    from app.models import Generic

    g = Generic(
        name="X",
        drug_class="Class",
        indications=["Use"],
        side_effects=["Effect"],
        precautions=["Care"],
        how_to_take=["With food"],
        drug_class_bn="শ্রেণি",
        indications_bn=["ব্যবহার"],
    )
    text, pending = _localized(g, "bn")
    assert text["drug_class"] == "শ্রেণি"
    assert text["indications"] == ["ব্যবহার"]
    assert text["side_effects"] == ["Effect"]
    assert pending == ["side_effects", "precautions", "how_to_take"]
    assert _localized(g, "en") == (
        {
            "drug_class": "Class",
            "indications": ["Use"],
            "side_effects": ["Effect"],
            "precautions": ["Care"],
            "how_to_take": ["With food"],
        },
        [],
    )


def test_empty_fields_are_not_pending_translation() -> None:
    from app.api.generics import _localized
    from app.models import Generic

    # how_to_take is empty when the source says nothing; there is nothing to translate.
    g = Generic(name="Y", drug_class="Class", indications=["Use"], side_effects=[], precautions=[])
    text, pending = _localized(g, "bn")
    assert text["how_to_take"] == []  # never stored on this object: treated as empty
    assert pending == ["drug_class", "indications"]


def test_generic_detail_has_how_to_take_from_the_seed(client: TestClient) -> None:
    by_name = {}
    for gid in range(1, 60):
        r = client.get(f"/api/generics/{gid}")
        if r.status_code == 200:
            by_name[r.json()["data"]["name"]] = r.json()["data"]
    cipro = by_name["Ciprofloxacin"]["how_to_take"]
    assert any("dairy products" in line for line in cipro)
    assert all("how_to_take" in g for g in by_name.values())
    # No dose instructions slipped in: the lines are about food, milk, alcohol and timing only.
    # A tablet strength naming which tablets a sentence is about ("120mg or 180mg fexofenadine
    # tablets, take them before a meal") is not a dose.
    dose = r"\b(once|twice|\d+ times) a day\b|\bdoses?\b|\btake \d+\b|\bup to \d+\b"
    for name, g in by_name.items():
        for line in g["how_to_take"]:
            assert not re.search(dose, line, re.I), (name, line)


def test_list_generics_with_presentations(client: TestClient) -> None:
    r = client.get("/api/generics")
    assert r.status_code == 200
    items = r.json()["data"]
    seed = get_settings().seed_dir
    generics = json.loads((seed / "generics.json").read_text(encoding="utf-8"))["records"]
    brands = json.loads((seed / "brands.json").read_text(encoding="utf-8"))["records"]
    groups = {(b["generic"], b["strength"], b["dosage_form"]) for b in brands}
    assert len(items) == len(generics)
    assert [g["name"] for g in items] == sorted(g["name"] for g in items)
    assert sum(len(g["presentations"]) for g in items) == len(groups)  # every compared group
    omeprazole = next(g for g in items if g["name"] == "Omeprazole")
    assert {"strength": "20 mg", "dosage_form": "capsule"}.items() <= omeprazole["presentations"][
        0
    ].items()
