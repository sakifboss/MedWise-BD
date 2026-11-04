"""Security headers on API responses."""

from fastapi.testclient import TestClient


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    for path in ("/api/health", "/api/search?q=napa", "/api/generics/99999"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert "max-age=" in headers["strict-transport-security"]
        assert headers["content-security-policy"].startswith("default-src 'none'")


def test_docs_keep_working_without_the_api_csp(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_cors_still_closed_to_other_sites(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
