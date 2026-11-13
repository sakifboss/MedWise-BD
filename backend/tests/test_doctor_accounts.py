"""R2: doctor accounts. Hashing, sessions, cookie flags, lockout, request checks, status changes,
password reset, export, deletion, the admin script, and nothing secret in the logs."""

import logging
import re
from collections.abc import Iterator
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import get_db, make_engine
from app.core.migrations import upgrade_durable_tables
from app.main import app
from app.models import Doctor, DoctorChamber, DoctorPasswordReset, DoctorSession
from app.services import passwords
from app.services.doctor_auth import COOKIE_NAME, FailureGuard, utcnow
from scripts import doctors as admin

SECRET = "test-frontend-secret"
SITE = "https://medwise-bd.vercel.app"
PASSWORD = "chamber-lamp-river-42"

PROFILE = {
    "display_name": "Dr. Rahima Khatun",
    "degrees": "MBBS, FCPS (Medicine)",
    "specialty": "Medicine",
    "bmdc_number": "a-12345",
    "phone": "01711-000000",
}


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'doctors.sqlite').as_posix()}")
    upgrade_durable_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def api(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(passwords, "N", 2**10)  # fast hashing in tests (the real N is tested below)
    monkeypatch.setattr(get_settings(), "frontend_shared_secret", SECRET)
    monkeypatch.setattr(get_settings(), "site_origins", f"{SITE},http://localhost:3000")
    make = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with make() as session:
            yield session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override
    headers = {"X-MedWise-Frontend": SECRET, "Origin": SITE}
    with TestClient(app, base_url="https://testserver", headers=headers) as client:
        yield client
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def signup(api: TestClient, email: str = "Rahima@Example.com", **extra: str) -> dict:
    r = api.post(
        "/api/doctor/signup", json={**PROFILE, "email": email, "password": PASSWORD, **extra}
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


def login(api: TestClient, email: str = "rahima@example.com", password: str = PASSWORD):  # noqa: ANN201
    return api.post("/api/doctor/login", json={"email": email, "password": password})


def set_cookie(response) -> SimpleCookie:  # noqa: ANN001
    jar: SimpleCookie = SimpleCookie()
    jar.load(response.headers["set-cookie"])
    return jar


def doctor_row(engine: Engine, email: str = "rahima@example.com") -> Doctor:
    with Session(engine, expire_on_commit=False) as db:
        found = db.scalar(select(Doctor).where(Doctor.email == email))
        assert found is not None
        return found


# ---------------------------------------------------------------- hashing and rules


def test_hash_format_salt_and_constant_parameters() -> None:
    first, second = passwords.hash_password(PASSWORD), passwords.hash_password(PASSWORD)
    assert re.fullmatch(r"scrypt\$16384\$8\$5\$[A-Za-z0-9+/=]{24}\$[A-Za-z0-9+/=]{44}", first)
    assert first != second  # a new random salt each time
    assert passwords.verify_password(PASSWORD, first)
    assert not passwords.verify_password(PASSWORD + "x", first)
    assert not passwords.needs_rehash(first)


def test_old_parameters_still_verify_and_ask_for_a_rehash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passwords, "N", 2**10)
    old = passwords.hash_password(PASSWORD)
    monkeypatch.undo()
    assert passwords.verify_password(PASSWORD, old)
    assert passwords.needs_rehash(old)
    assert not passwords.verify_password(PASSWORD, "argon2id$v=19$whatever")  # unknown scheme
    assert not passwords.verify_password(PASSWORD, "garbage")


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("short-pw", "password_too_short"),
        ("x" * 129, "password_too_long"),
        ("qwertyuiop", "password_common"),
        ("1234567890", "password_common"),
        ("rahima.khatun", "password_personal"),  # the email's local part
        ("DrRahimaKhatun", None),  # not exactly the name with spaces removed
        (PASSWORD, None),
    ],
)
def test_password_rules(password: str, problem: str | None) -> None:
    assert passwords.password_problem(password, "rahima.khatun@example.com", "Dr Rahima") == problem


# ---------------------------------------------------------------- sign up, cookie, checks


def test_signup_creates_a_pending_account_and_logs_in(api: TestClient, engine: Engine) -> None:
    data = signup(api)
    assert data["email"] == "rahima@example.com"  # lowercased
    assert data["bmdc_number"] == "A-12345"
    assert (data["status"], data["is_demo"], data["chambers"]) == ("pending", False, [])
    me = api.get("/api/doctor/me")
    assert me.status_code == 200 and me.json()["data"]["display_name"] == "Dr. Rahima Khatun"
    assert me.headers["cache-control"] == "no-store"
    row = doctor_row(engine)
    assert row.password_hash.startswith("scrypt$") and PASSWORD not in row.password_hash
    assert row.last_login_day == utcnow().date()


def test_session_cookie_flags(api: TestClient) -> None:
    r = api.post(
        "/api/doctor/signup", json={**PROFILE, "email": "a@example.com", "password": PASSWORD}
    )
    cookie = set_cookie(r)[COOKIE_NAME]
    header = r.headers["set-cookie"].lower()
    assert cookie["httponly"] and cookie["secure"] and cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/" and "domain=" not in header
    assert int(cookie["max-age"]) == 7 * 24 * 3600
    assert len(cookie.value) >= 40  # 32 random bytes


def test_cookie_is_not_secure_on_localhost(api: TestClient) -> None:
    r = api.post(
        "/api/doctor/signup",
        json={**PROFILE, "email": "local@example.com", "password": PASSWORD},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 201
    assert not set_cookie(r)[COOKIE_NAME]["secure"]


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "https://medwise-bd-git-feature-team.vercel.app"},  # previews are not allowed
        {"Origin": ""},
        {"X-MedWise-Frontend": "wrong"},
    ],
)
def test_changes_need_our_origin_and_the_frontend_secret(
    api: TestClient, headers: dict[str, str]
) -> None:
    r = api.post(
        "/api/doctor/signup",
        json={**PROFILE, "email": "x@example.com", "password": PASSWORD},
        headers=headers,
    )
    assert r.status_code == 403


def test_reads_need_the_frontend_secret_and_a_login(api: TestClient) -> None:
    assert api.get("/api/doctor/me").status_code == 401
    assert api.get("/api/doctor/me").headers["cache-control"] == "no-store"
    signup(api)
    assert api.get("/api/doctor/me", headers={"X-MedWise-Frontend": "wrong"}).status_code == 403


def test_signup_validation_duplicates_and_limit(api: TestClient) -> None:
    signup(api)
    again = api.post(
        "/api/doctor/signup", json={**PROFILE, "email": "RAHIMA@example.com", "password": PASSWORD}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "email_taken"
    weak = api.post(
        "/api/doctor/signup", json={**PROFILE, "email": "w@example.com", "password": "qwertyuiop"}
    )
    assert weak.json()["error"]["code"] == "password_common"
    bad = api.post(
        "/api/doctor/signup",
        json={**PROFILE, "email": "not-an-email", "password": PASSWORD, "extra": "x"},
    )
    assert bad.status_code == 422
    for i in range(10):  # 5 sign-ups an hour per client (counting the ones above)
        last = api.post(
            "/api/doctor/signup",
            json={**PROFILE, "email": f"n{i}@example.com", "password": PASSWORD},
        )
    assert last.status_code == 429


# ---------------------------------------------------------------- log in and lockout


def test_login_has_one_message_for_unknown_email_and_wrong_password(api: TestClient) -> None:
    signup(api)
    api.cookies.clear()
    wrong = login(api, password="not-the-password-1")
    unknown = login(api, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"] == unknown.json()["error"]
    ok = login(api, email=" Rahima@Example.com ")
    assert ok.status_code == 200 and COOKIE_NAME in ok.headers["set-cookie"]


def test_five_failures_lock_the_email_for_15_minutes(api: TestClient) -> None:
    signup(api)
    for _ in range(5):
        assert login(api, password="not-the-password-1").status_code == 401
    locked = login(api)  # even the right password waits
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "login_locked"


def test_twenty_failures_lock_the_client() -> None:
    now = [0.0]
    guard = FailureGuard(20, 900, clock=lambda: now[0])
    for _ in range(19):
        guard.fail("1.2.3.4")
    assert not guard.locked("1.2.3.4")
    guard.fail("1.2.3.4")
    assert guard.locked("1.2.3.4") and not guard.locked("5.6.7.8")
    now[0] = 899
    assert guard.locked("1.2.3.4")
    now[0] = 901  # 15 minutes after the failures
    assert not guard.locked("1.2.3.4")


# ---------------------------------------------------------------- sessions


def test_session_idle_and_absolute_expiry(api: TestClient, engine: Engine) -> None:
    signup(api)
    assert api.get("/api/doctor/me").status_code == 200
    with Session(engine) as db:
        session = db.scalar(select(DoctorSession))
        assert session is not None
        session.last_seen = utcnow() - timedelta(hours=12, minutes=1)
        db.commit()
    assert api.get("/api/doctor/me").status_code == 401  # 12 hours without use
    login(api)
    with Session(engine) as db:
        session = db.scalar(select(DoctorSession))
        assert session is not None
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert api.get("/api/doctor/me").status_code == 401  # 7 days after login
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DoctorSession)) == 0  # cleaned up


def test_logout_and_logout_everywhere(api: TestClient, engine: Engine) -> None:
    signup(api)
    other = TestClient(app, base_url="https://testserver", headers=dict(api.headers))
    assert login(other).status_code == 200
    assert api.post("/api/doctor/logout").status_code == 200
    assert api.get("/api/doctor/me").status_code == 401
    assert other.get("/api/doctor/me").status_code == 200
    login(api)
    assert api.post("/api/doctor/logout-all").status_code == 200
    assert other.get("/api/doctor/me").status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(DoctorSession)) == 0


# ---------------------------------------------------------------- profile and chambers


def test_changing_the_bmdc_number_or_name_needs_a_new_check(
    api: TestClient, engine: Engine
) -> None:
    signup(api)
    with Session(engine) as db:
        assert admin.cmd_verify(db, "rahima@example.com", ask=_answers("y", "y", "SB", "phone"))
    profile = {**PROFILE, "specialty": "Cardiology"}
    kept = api.post("/api/doctor/profile", json=profile).json()["data"]
    assert (kept["status"], kept["specialty"], kept["verified_on"]) == (
        "verified",
        "Cardiology",
        str(utcnow().date()),
    )
    changed = api.post("/api/doctor/profile", json={**profile, "bmdc_number": "A-54321"})
    assert changed.json()["data"]["status"] == "pending"
    assert doctor_row(engine).verified_by is None
    with Session(engine) as db:
        admin.cmd_verify(db, "rahima@example.com", ask=_answers("y", "y", "SB", "phone"))
    renamed = api.post("/api/doctor/profile", json={**profile, "display_name": "Dr. Someone Else"})
    assert renamed.json()["data"]["status"] == "pending"


def test_chambers_at_most_three(api: TestClient) -> None:
    signup(api)
    chamber = {
        "name": "Popular Diagnostic",
        "address": "Zindabazar, Sylhet",
        "hours": "Sat-Thu 5-9 pm",
    }
    saved = api.post("/api/doctor/chambers", json={"chambers": [chamber, {**chamber, "phone": ""}]})
    assert [c["name"] for c in saved.json()["data"]["chambers"]] == ["Popular Diagnostic"] * 2
    assert saved.json()["data"]["chambers"][1]["phone"] is None
    too_many = api.post("/api/doctor/chambers", json={"chambers": [chamber] * 4})
    assert too_many.status_code == 422
    cleared = api.post("/api/doctor/chambers", json={"chambers": []})
    assert cleared.json()["data"]["chambers"] == []


# ---------------------------------------------------------------- passwords


def test_change_password_logs_out_other_devices(api: TestClient) -> None:
    signup(api)
    other = TestClient(app, base_url="https://testserver", headers=dict(api.headers))
    login(other)
    wrong = api.post(
        "/api/doctor/password",
        json={"current_password": "not-it-at-all", "new_password": "a-new-long-password-7"},
    )
    assert wrong.status_code == 403
    ok = api.post(
        "/api/doctor/password",
        json={"current_password": PASSWORD, "new_password": "a-new-long-password-7"},
    )
    assert ok.status_code == 200
    assert api.get("/api/doctor/me").status_code == 200  # this device stays logged in
    assert other.get("/api/doctor/me").status_code == 401
    api.cookies.clear()
    assert login(api).status_code == 401
    assert login(api, password="a-new-long-password-7").status_code == 200


def _reset_token(engine: Engine) -> str:
    with Session(engine) as db:
        lines = admin.cmd_reset_link(db, "rahima@example.com", "https://site.example")
    link = lines[-1]
    assert link.startswith("https://site.example/doctor/reset#")
    return link.split("#", 1)[1]


def test_reset_link_works_once_within_60_minutes(api: TestClient, engine: Engine) -> None:
    signup(api)
    token = _reset_token(engine)
    with Session(engine) as db:
        stored = db.scalar(select(DoctorPasswordReset.token_hash))
    assert stored != token and len(stored or "") == 64  # only the hash is stored
    body = {"token": token, "new_password": "brand-new-password-9"}
    assert api.post("/api/doctor/reset", json=body).status_code == 200
    assert api.get("/api/doctor/me").status_code == 401  # every session ended
    again = api.post("/api/doctor/reset", json=body)
    assert again.status_code == 400 and again.json()["error"]["code"] == "reset_invalid"
    assert login(api, password="brand-new-password-9").status_code == 200

    late = _reset_token(engine)
    with Session(engine) as db:
        for reset in db.scalars(select(DoctorPasswordReset)):
            reset.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    expired = api.post(
        "/api/doctor/reset", json={"token": late, "new_password": "x-another-one-11"}
    )
    assert expired.status_code == 400


# ---------------------------------------------------------------- export and delete


def test_export_has_everything_but_no_secrets(api: TestClient) -> None:
    signup(api)
    r = api.get("/api/doctor/export")
    data = r.json()["data"]
    assert data["profile"]["email"] == "rahima@example.com" and data["active_sessions"] == 1
    assert "scrypt" not in r.text and PASSWORD not in r.text
    assert "patients" in data["note"]


def test_delete_account_removes_every_row(api: TestClient, engine: Engine) -> None:
    signup(api)
    chamber = {"name": "Chamber", "address": "Sylhet", "hours": "Daily"}
    api.post("/api/doctor/chambers", json={"chambers": [chamber]})
    _reset_token(engine)
    assert api.post("/api/doctor/delete", json={"password": "wrong-password-1"}).status_code == 403
    r = api.post("/api/doctor/delete", json={"password": PASSWORD})
    assert r.status_code == 200 and f"{COOKIE_NAME}=" in r.headers["set-cookie"]
    with Session(engine) as db:
        for model in (Doctor, DoctorChamber, DoctorSession, DoctorPasswordReset):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model
    assert api.get("/api/doctor/me").status_code == 401


# ---------------------------------------------------------------- logs


def test_no_password_email_or_token_in_the_logs(
    api: TestClient, engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    signup(api)
    login(api, password="wrong-password-123")
    ok = login(api)
    token = set_cookie(ok)[COOKIE_NAME].value
    reset = _reset_token(engine)
    api.post("/api/doctor/reset", json={"token": reset, "new_password": "brand-new-password-9"})
    for secret in (PASSWORD, "wrong-password-123", "brand-new-password-9", token, reset):
        assert secret not in caplog.text
    assert "rahima@example.com" not in caplog.text


# ---------------------------------------------------------------- admin script


def _answers(*replies: str):  # noqa: ANN202
    queue = list(replies)
    return lambda _prompt: queue.pop(0)


def test_verify_needs_every_check_initials_and_method(api: TestClient, engine: Engine) -> None:
    signup(api)
    with Session(engine) as db:
        for replies in (("y", "n"), ("n",), ("y", "y", "", "phone"), ("y", "y", "SB", " ")):
            with pytest.raises(admin.Stop):
                admin.cmd_verify(db, "rahima@example.com", ask=_answers(*replies))
        assert doctor_row(engine).status == "pending"
        admin.cmd_verify(db, "rahima@example.com", ask=_answers("y", "y", "SB", "called chamber"))
    row = doctor_row(engine)
    assert (row.status, row.verified_by, row.verify_method) == ("verified", "SB", "called chamber")
    assert api.get("/api/doctor/me").json()["data"]["status"] == "verified"


def test_reject_shows_the_reason(api: TestClient, engine: Engine) -> None:
    signup(api)
    with Session(engine) as db:
        admin.cmd_reject(db, "rahima@example.com", "The BMDC number does not match the name.")
    data = api.get("/api/doctor/me").json()["data"]
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "The BMDC number does not match the name."


def test_demo_accounts_and_delete(api: TestClient, engine: Engine) -> None:
    with Session(engine) as db:
        lines = admin.cmd_create_demo(db, "Demo@Example.com", "Dr. Demo")
        password = lines[-1].split(": ", 1)[1]
        with pytest.raises(admin.Stop):
            admin.cmd_verify(db, "demo@example.com", ask=_answers("y", "y", "SB", "x"))
    data = login(api, email="demo@example.com", password=password).json()["data"]
    assert data["is_demo"] and data["status"] == "pending"
    with Session(engine) as db:
        with pytest.raises(admin.Stop):
            admin.cmd_delete(db, "demo@example.com", ask=_answers("wrong@example.com"))
        assert admin.cmd_delete(db, "demo@example.com", ask=_answers("demo@example.com")) == [
            "Deleted."
        ]
    assert api.get("/api/doctor/me").status_code == 401


def test_list_and_show(api: TestClient, engine: Engine) -> None:
    signup(api)
    with Session(engine) as db:
        assert "Dr. Rahima Khatun" in admin.cmd_list(db, "pending")[0]
        assert admin.cmd_list(db, "verified") == ["No doctors."]
        assert "MBBS, FCPS" in "\n".join(admin.cmd_show(db, "1"))
        with pytest.raises(admin.Stop):
            admin.cmd_show(db, "999")
