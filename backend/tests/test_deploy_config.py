import pytest
from fastapi.testclient import TestClient

from app.api import prescription
from app.api.prescription import get_extractor
from app.core.db import normalize_database_url
from app.core.rate_limit import RateLimiter
from app.main import app

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./medwise.db", "sqlite:///./medwise.db"),
    ],
)
def test_normalize_database_url(url: str, expected: str) -> None:
    assert normalize_database_url(url) == expected


def test_rate_limiter_sliding_window() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")  # separate key
    now[0] = 61
    assert limiter.allow("a")  # window has passed


@pytest.fixture
def limited_client(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(prescription, "per_client_limiter", RateLimiter(2, 3600))
    monkeypatch.setattr(prescription, "global_limiter", RateLimiter(3, 86400))
    app.dependency_overrides[get_extractor] = lambda: lambda image, mime: []
    yield client
    app.dependency_overrides.pop(get_extractor, None)


def _post(client: TestClient, ip: str):
    return client.post(
        "/api/prescription",
        files={"image": ("rx.jpg", JPEG, "image/jpeg")},
        headers={"X-Forwarded-For": f"{ip}, 10.0.0.1"},
    )


def test_prescription_per_client_limit(limited_client: TestClient) -> None:
    assert _post(limited_client, "1.1.1.1").status_code == 200
    assert _post(limited_client, "1.1.1.1").status_code == 200
    blocked = _post(limited_client, "1.1.1.1")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert _post(limited_client, "2.2.2.2").status_code == 200  # other client unaffected


def test_prescription_global_daily_limit(limited_client: TestClient) -> None:
    for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        assert _post(limited_client, ip).status_code == 200
    blocked = _post(limited_client, "4.4.4.4")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "ocr_busy"
