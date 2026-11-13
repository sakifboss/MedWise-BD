# ruff: noqa: F811  (fixtures shared with test_doctor_accounts)
"""R4: signing prescription QR codes and checking them. Only a hash reaches the server; nothing is
stored or logged about the prescription."""

import hashlib
import logging
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api import doctor as doctor_api
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.services import rx_signing
from scripts import doctors as admin
from tests.test_doctor_accounts import SECRET, api, engine, signup  # noqa: F401

RX_SECRET = "test-rx-signing-secret-0123456789"
PAYLOAD = '{"v":1,"d":"2026-11-13","f":"","l":[[1,"1+0+1",0,2,"5d",1]]}'
HASH = hashlib.sha256(PAYLOAD.encode()).hexdigest()


@pytest.fixture(autouse=True)
def rx_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "rx_signing_secret", RX_SECRET)


def sign(api: TestClient, payload_hash: str = HASH):  # noqa: ANN201
    return api.post("/api/doctor/rx/sign", json={"hash": payload_hash})


def verify(api: TestClient, **body):  # noqa: ANN003, ANN201
    return api.post("/api/rx/verify", json=body)


def test_hmac_sign_and_verify() -> None:
    sig = rx_signing.sign(RX_SECRET, 7, 1794586743, HASH)
    assert len(sig) == 43 and rx_signing.verify(RX_SECRET, 7, 1794586743, HASH, sig)
    assert not rx_signing.verify("another-secret", 7, 1794586743, HASH, sig)
    assert not rx_signing.verify("", 7, 1794586743, HASH, sig)
    assert not rx_signing.verify(
        RX_SECRET, 7, 1794586743, HASH, sig[:-1] + ("A" if sig[-1] != "A" else "B")
    )
    assert not rx_signing.verify(RX_SECRET, 7, 1794586743, "nothex", sig)


def test_sign_needs_a_logged_in_doctor(api: TestClient) -> None:
    assert sign(api).status_code == 401
    signup(api)
    r = sign(api)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    data = r.json()["data"]
    assert abs(data["issued_at"] - time.time()) < 5
    assert rx_signing.verify(RX_SECRET, data["doctor_id"], data["issued_at"], HASH, data["sig"])
    assert sign(api, "not-a-hash").status_code == 422
    other_origin = api.post(
        "/api/doctor/rx/sign", json={"hash": HASH}, headers={"Origin": "https://evil.example"}
    )
    assert other_origin.status_code == 403


def test_sign_is_off_without_a_secret(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    signup(api)
    monkeypatch.setattr(get_settings(), "rx_signing_secret", "")
    r = sign(api)
    assert r.status_code == 503 and r.json()["error"]["code"] == "signing_unavailable"


def test_rejected_doctors_cannot_sign(api: TestClient, engine: Engine) -> None:  # noqa: F811
    signup(api)
    with Session(engine) as db:
        admin.cmd_reject(db, "rahima@example.com", "Name does not match")
    assert sign(api).status_code == 403


def test_daily_limit_per_doctor(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_api, "rx_sign_limiter", RateLimiter(2, 86400))
    signup(api)
    assert [sign(api).status_code for _ in range(3)] == [200, 200, 429]


def test_verify_valid_tampered_and_states(api: TestClient, engine: Engine) -> None:  # noqa: F811
    signup(api)
    s = sign(api).json()["data"]
    body = {"doctor_id": s["doctor_id"], "issued_at": s["issued_at"], "hash": HASH, "sig": s["sig"]}
    ok = verify(api, **body).json()["data"]
    assert ok["valid"] and ok["doctor"]["display_name"] == "Dr. Rahima Khatun"
    assert ok["doctor"]["status"] == "pending" and not ok["doctor"]["is_demo"]
    assert "email" not in ok["doctor"]
    tampered = hashlib.sha256((PAYLOAD + " ").encode()).hexdigest()
    for change in (
        {"hash": tampered},
        {"doctor_id": s["doctor_id"] + 1},
        {"issued_at": s["issued_at"] - 1},
    ):
        assert verify(api, **{**body, **change}).json()["data"] == {"valid": False, "doctor": None}
    future = rx_signing.sign(RX_SECRET, s["doctor_id"], int(time.time()) + 3600, HASH)
    assert not verify(api, **{**body, "issued_at": int(time.time()) + 3600, "sig": future}).json()[
        "data"
    ]["valid"]
    ANSWERS = iter(["y", "y", "SB", "phone"])  # noqa: N806
    with Session(engine) as db:
        admin.cmd_verify(
            db,
            "rahima@example.com",
            ask=lambda _p: next(ANSWERS),
        )
    assert verify(api, **body).json()["data"]["doctor"]["status"] == "verified"
    with Session(engine) as db:
        admin.cmd_delete(db, "rahima@example.com", ask=lambda _: "rahima@example.com")
    assert not verify(api, **body).json()["data"][
        "valid"
    ]  # deleted account: nobody stands behind it


def test_demo_qr_says_demo(api: TestClient, engine: Engine) -> None:  # noqa: F811
    with Session(engine) as db:
        password = admin.cmd_create_demo(db, "demo@example.com", "Dr. Demo")[-1].split(": ", 1)[1]
    api.post("/api/doctor/login", json={"email": "demo@example.com", "password": password})
    s = sign(api).json()["data"]
    body = {"doctor_id": s["doctor_id"], "issued_at": s["issued_at"], "hash": HASH, "sig": s["sig"]}
    assert verify(api, **body).json()["data"]["doctor"]["is_demo"] is True


def test_verify_needs_our_frontend_and_is_rate_limited(api: TestClient) -> None:
    body = {"doctor_id": 1, "issued_at": 1, "hash": HASH, "sig": "x" * 43}
    first = verify(api, **body)
    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
    assert (
        api.post("/api/rx/verify", json=body, headers={"X-MedWise-Frontend": "no"}).status_code
        == 403
    )
    codes = [verify(api, **body).status_code for _ in range(30)]  # 30 a minute per client
    assert codes[-1] == 429 and codes[-2] == 200


def test_nothing_about_the_prescription_is_logged(
    api: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    signup(api)
    s = sign(api).json()["data"]
    verify(api, doctor_id=s["doctor_id"], issued_at=s["issued_at"], hash=HASH, sig=s["sig"])
    assert HASH not in caplog.text and s["sig"] not in caplog.text
