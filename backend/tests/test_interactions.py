from typing import Any

from fastapi.testclient import TestClient

URL = "/api/interactions/check"


def _id(client: TestClient, name: str, kind: str, strength: str | None = None) -> int:
    results = client.get("/api/search", params={"q": name}).json()["data"]["results"]
    return next(
        r["id"]
        for r in results
        if r["type"] == kind
        and r["name"] == name
        and (strength is None or r["strength"] == strength)
    )


def generic(client: TestClient, name: str) -> int:
    return _id(client, name, "generic")


def brand(client: TestClient, name: str, strength: str) -> int:
    return _id(client, name, "brand", strength)


def check(client: TestClient, **body: Any) -> dict:
    response = client.post(URL, json=body)
    assert response.status_code == 200, response.json()
    return response.json()["data"]


def pairs(data: dict) -> list[tuple[str, str, str]]:
    return [
        (*sorted((i["generic_a"]["name"], i["generic_b"]["name"])), i["severity"])
        for i in data["interactions"]
    ]


def test_finds_interaction_between_generics(client: TestClient) -> None:
    data = check(client, generic_ids=[generic(client, "Warfarin"), generic(client, "Aspirin")])
    assert pairs(data) == [("Aspirin", "Warfarin", "major")]
    assert data["pairs_checked"] == 1
    assert "Consult your doctor" in data["disclaimer"]


def test_brands_are_resolved_to_generics(client: TestClient) -> None:
    # Clotrex = clopidogrel, Omezol = omeprazole (major interaction in seed data)
    data = check(
        client, brand_ids=[brand(client, "Clotrex", "75 mg"), brand(client, "Omezol", "20 mg")]
    )
    assert pairs(data) == [("Clopidogrel", "Omeprazole", "major")]
    brands = {m["generic_name"]: m["brands"] for m in data["medicines"]}
    assert brands == {"Clopidogrel": ["Clotrex"], "Omeprazole": ["Omezol"]}


def test_mixed_brands_and_generics_sorted_by_severity(client: TestClient) -> None:
    data = check(
        client,
        brand_ids=[brand(client, "Cholvas", "10 mg")],  # atorvastatin
        generic_ids=[
            generic(client, "Amlodipine"),
            generic(client, "Warfarin"),
            generic(client, "Metronidazole"),
        ],
    )
    assert pairs(data) == [
        ("Metronidazole", "Warfarin", "major"),
        ("Atorvastatin", "Metronidazole", "moderate"),
        ("Atorvastatin", "Warfarin", "minor"),
    ]
    assert data["pairs_checked"] == 6  # 4 medicines


def test_no_recorded_interactions(client: TestClient) -> None:
    data = check(
        client, generic_ids=[generic(client, "Cetirizine"), generic(client, "Montelukast")]
    )
    assert data["interactions"] == []
    assert "does not mean it is safe" in data["note"]


def test_single_medicine_checks_no_pairs(client: TestClient) -> None:
    data = check(client, generic_ids=[generic(client, "Warfarin")])
    assert data["interactions"] == []
    assert data["pairs_checked"] == 0


def test_duplicate_generic_via_two_brands(client: TestClient) -> None:
    data = check(
        client,
        brand_ids=[brand(client, "Pyrolin", "500 mg"), brand(client, "Dimol", "500 mg")],
    )
    assert [(d["generic_name"], sorted(d["brands"])) for d in data["duplicates"]] == [
        ("Paracetamol", ["Dimol", "Pyrolin"])
    ]
    assert len(data["medicines"]) == 1


def test_same_brand_twice_is_not_a_duplicate(client: TestClient) -> None:
    pyrolin_tab = brand(client, "Pyrolin", "500 mg")
    pyrolin_syrup = brand(client, "Pyrolin", "120 mg/5 ml")
    data = check(client, brand_ids=[pyrolin_tab, pyrolin_tab, pyrolin_syrup])
    assert data["duplicates"] == []


def test_unknown_ids_are_reported(client: TestClient) -> None:
    response = client.post(URL, json={"brand_ids": [99999], "generic_ids": [1]})
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Unknown brand id(s): 99999",
        "details": None,
    }


def test_empty_request_is_rejected(client: TestClient) -> None:
    response = client.post(URL, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_too_many_medicines(client: TestClient) -> None:
    response = client.post(URL, json={"generic_ids": list(range(1, 21)), "brand_ids": [1]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_medicines"
