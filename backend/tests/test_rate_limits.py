"""Rate limits on search and the interaction check, and whose address they trust.

The production headers below were observed on the live site: requests our frontend proxies arrive
with x-vercel-forwarded-for (the visitor), every request to Render has cf-connecting-ip, and
X-Forwarded-For carries whatever the client put in it first.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import client_key

SECRET = "rate-limit-test-secret"


def _search(client: TestClient, **headers: str):
    named = {k.replace("_", "-"): v for k, v in headers.items()}
    return client.get("/api/search", params={"q": "napa"}, headers=named)


def _request(**headers: str) -> Request:
    raw = [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": ("10.9.9.9", 1)})


def test_search_allows_people_and_stops_floods(client: TestClient) -> None:
    limit = get_settings().search_limit_per_minute
    for _ in range(limit):
        assert _search(client, x_forwarded_for="203.0.113.5").status_code == 200
    blocked = _search(client, x_forwarded_for="203.0.113.5")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert _search(client, x_forwarded_for="198.51.100.7").status_code == 200  # someone else


def test_interaction_check_is_limited(client: TestClient) -> None:
    body = {"generic_ids": [1, 2]}
    headers = {"X-Forwarded-For": "203.0.113.9"}
    for _ in range(get_settings().interactions_limit_per_minute):
        assert client.post("/api/interactions/check", json=body, headers=headers).status_code == 200
    assert client.post("/api/interactions/check", json=body, headers=headers).status_code == 429


@pytest.fixture
def locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)


def test_forged_addresses_on_direct_calls_do_not_escape_the_limit(
    client: TestClient, locked: None
) -> None:
    limit = get_settings().search_limit_per_minute
    for i in range(limit):
        forged = f"10.0.{i // 250}.{i % 250}, 203.0.113.5, 104.23.160.{i % 250}"
        response = _search(client, x_forwarded_for=forged, cf_connecting_ip="203.0.113.5")
        assert response.status_code == 200
    assert (
        _search(client, x_forwarded_for="10.99.99.99", cf_connecting_ip="203.0.113.5").status_code
        == 429
    )


def test_frontend_requests_are_limited_per_visitor(client: TestClient, locked: None) -> None:
    limit = get_settings().search_limit_per_minute
    for i in range(limit):
        response = _search(
            client,
            x_medwise_frontend=SECRET,
            x_vercel_forwarded_for="203.0.113.5",
            x_forwarded_for=f"10.0.{i // 250}.{i % 250}",  # forged by the visitor, ignored
            cf_connecting_ip="54.179.25.192",  # Vercel's own address, shared by all visitors
        )
        assert response.status_code == 200
    common = {"x_medwise_frontend": SECRET, "cf_connecting_ip": "54.179.25.192"}
    assert _search(client, x_vercel_forwarded_for="203.0.113.5", **common).status_code == 429
    assert _search(client, x_vercel_forwarded_for="198.51.100.7", **common).status_code == 200


def test_client_key_rules(locked: None) -> None:
    vercel = {"x_vercel_forwarded_for": "203.0.113.5", "cf_connecting_ip": "54.179.25.192"}
    assert client_key(_request(x_medwise_frontend=SECRET, **vercel)) == "203.0.113.5"
    # Without the secret, a Vercel header could be sent by anyone: use Cloudflare's address.
    assert client_key(_request(**vercel)) == "54.179.25.192"
    assert (
        client_key(
            _request(x_forwarded_for="10.1.2.3, 198.51.100.7", cf_connecting_ip="198.51.100.7")
        )
        == "198.51.100.7"
    )
    assert client_key(_request()) == "10.9.9.9"


def test_local_runs_fall_back_to_forwarded_for() -> None:
    # No Vercel or Cloudflare in front (dev server, Docker, tests) and no secret configured.
    assert client_key(_request(x_forwarded_for="203.0.113.5, 10.0.0.1")) == "203.0.113.5"
