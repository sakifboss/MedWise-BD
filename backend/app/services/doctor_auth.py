"""Doctor sessions, the login lockout and the request checks for /api/doctor.

Sessions: the cookie holds a random 32-byte token; the database keeps only its sha256. A session
ends after 12 hours without use or 7 days after login, whichever comes first, on logout, and for
every device on "log out everywhere", a password change or reset, and account deletion.

Cookie mw_doc: HttpOnly, SameSite=Lax, Path=/, no Domain attribute (only our site), Secure except
on http://localhost (local development and Docker).

Requests that change anything must come through our frontend (shared-secret header) and carry an
Origin that is one of our sites (settings.site_origins: the live site, localhost). Vercel preview
sites are not allowed on purpose: previews use the production API and database.
"""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.models import Doctor, DoctorSession

COOKIE_NAME = "mw_doc"
IDLE = timedelta(hours=12)
ABSOLUTE = timedelta(days=7)
LAST_SEEN_STEP = timedelta(minutes=1)  # write last_seen at most once a minute
RESET_VALID = timedelta(minutes=60)

LOCKOUT = 15 * 60  # seconds
FAILURES_PER_EMAIL = 5
FAILURES_PER_CLIENT = 20


def utcnow() -> datetime:
    """Naive UTC (the columns are timezone-less; every time stored is UTC)."""
    return datetime.now(UTC).replace(tzinfo=None)


def new_token() -> tuple[str, str]:
    """(token for the cookie or link, sha256 hex to store)."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- lockout


class FailureGuard:
    """Counts failed logins per key; at `limit` failures within the window the key waits
    `window` seconds from the last failure. In memory, like the other rate limits."""

    def __init__(
        self, limit: int, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        return failures

    def locked(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            failures = self._trim(key, now)
            return len(failures) >= self.limit and failures[-1] > now - self.window

    def fail(self, key: str) -> None:
        with self._lock:
            self._trim(key, self._clock()).append(self._clock())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


email_guard = FailureGuard(FAILURES_PER_EMAIL, LOCKOUT)
client_guard = FailureGuard(FAILURES_PER_CLIENT, LOCKOUT)


# ---------------------------------------------------------------- request checks


def allowed_origins() -> set[str]:
    return {o.strip().rstrip("/") for o in get_settings().site_origins.split(",") if o.strip()}


def require_same_site(request: Request) -> None:
    """State-changing doctor requests: our frontend's secret header and one of our Origins."""
    require_frontend(request)
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin not in allowed_origins():
        raise AppError(403, "forbidden", "This is only available on the MedWise BD website.")


def _is_local(request: Request) -> bool:
    origin = request.headers.get("origin") or ""
    return origin.startswith(("http://localhost", "http://127.0.0.1"))


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(ABSOLUTE.total_seconds()),
        path="/",
        httponly=True,
        secure=not _is_local(request),
        samesite="lax",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, secure=not _is_local(request), samesite="lax"
    )


# ---------------------------------------------------------------- sessions


def start_session(db: Session, doctor: Doctor) -> str:
    """A new session for the doctor; returns the cookie token. Also drops expired sessions."""
    now = utcnow()
    db.execute(
        delete(DoctorSession).where(
            (DoctorSession.expires_at <= now) | (DoctorSession.last_seen <= now - IDLE)
        )
    )
    token, hashed = new_token()
    db.add(
        DoctorSession(
            token_hash=hashed,
            doctor_id=doctor.id,
            created_at=now,
            last_seen=now,
            expires_at=now + ABSOLUTE,
        )
    )
    doctor.last_login_day = now.date()
    return token


def end_sessions(db: Session, doctor_id: int, keep: str | None = None) -> None:
    """End every session of the doctor (except the one with token hash `keep`)."""
    query = delete(DoctorSession).where(DoctorSession.doctor_id == doctor_id)
    if keep is not None:
        query = query.where(DoctorSession.token_hash != keep)
    db.execute(query)


def session_for(db: Session, token: str | None) -> DoctorSession | None:
    """The live session for a cookie token, or None (unknown, idle too long or expired)."""
    if not token:
        return None
    found = db.scalar(select(DoctorSession).where(DoctorSession.token_hash == token_hash(token)))
    now = utcnow()
    if found is None:
        return None
    if found.expires_at <= now or found.last_seen <= now - IDLE:
        db.delete(found)
        db.commit()
        return None
    if now - found.last_seen >= LAST_SEEN_STEP:
        found.last_seen = now
        db.commit()
    return found


def current_session(
    db: Annotated[Session, Depends(get_db)],
    mw_doc: Annotated[str | None, Cookie()] = None,
) -> DoctorSession:
    found = session_for(db, mw_doc)
    if found is None:
        raise AppError(401, "not_logged_in", "Please log in.")
    return found


def current_doctor(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[DoctorSession, Depends(current_session)],
) -> Doctor:
    doctor = db.get(Doctor, session.doctor_id)
    if doctor is None:
        raise AppError(401, "not_logged_in", "Please log in.")
    return doctor
