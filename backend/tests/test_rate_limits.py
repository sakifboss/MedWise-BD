"""Rate limits on search and the interaction check, and whose address they trust."""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import client_key

SECRET = "rate-limit-test-secret"


def _search(client: TestClient, forwarded: str, secret: str | None = None):
    headers = {"X-Forwarded-For": forwarded}
    if secret is not None:
        headers["X-MedWise-Frontend"] = secret
    return client.get("/api/search", params={"q": "napa"}, headers=headers)


def _request(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("10.9.9.9", 1)})


def test_search_allows_people_and_stops_floods(client: TestClient) -> None:
    limit = get_settings().search_limit_per_minute
    for _ in range(limit):
        assert _search(client, "203.0.113.5").status_code == 200
    blocked = _search(client, "203.0.113.5")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert _search(client, "198.51.100.7").status_code == 200  # someone else is not affected


def test_interaction_check_is_limited(client: TestClient) -> None:
    body = {"generic_ids": [1, 2]}
    headers = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(get_settings().interactions_limit_per_minute):
        assert client.post("/api/interactions/check", json=body, headers=headers).status_code == 200
    assert client.post("/api/interactions/check", json=body, headers=headers).status_code == 429


@pytest.fixture
def locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)


def test_forged_addresses_do_not_escape_the_limit(client: TestClient, locked: None) -> None:
    # Without the secret, the first X-Forwarded-For entry is attacker-controlled; only the last
    # entry (added by our hosting proxy) counts, so changing the first one does not help.
    limit = get_settings().search_limit_per_minute
    for i in range(limit):
        assert _search(client, f"10.0.{i // 250}.{i % 250}, 192.0.2.50").status_code == 200
    assert _search(client, "10.99.99.99, 192.0.2.50").status_code == 429


def test_frontend_requests_are_limited_per_real_client(client: TestClient, locked: None) -> None:
    limit = get_settings().search_limit_per_minute
    for _ in range(limit):
        assert _search(client, "203.0.113.5, 192.0.2.50", SECRET).status_code == 200
    assert _search(client, "203.0.113.5, 192.0.2.50", SECRET).status_code == 429
    # Another visitor behind the same proxy has their own allowance.
    assert _search(client, "198.51.100.7, 192.0.2.50", SECRET).status_code == 200


def test_client_key_rules(locked: None) -> None:
    trusted = {"X-Forwarded-For": "203.0.113.5, 192.0.2.50", "X-MedWise-Frontend": SECRET}
    assert client_key(_request(trusted)) == "203.0.113.5"
    assert client_key(_request({"X-Forwarded-For": "203.0.113.5, 192.0.2.50"})) == "192.0.2.50"
    assert client_key(_request({})) == "10.9.9.9"


def test_without_a_secret_the_first_address_is_used() -> None:
    assert client_key(_request({"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})) == "203.0.113.5"
