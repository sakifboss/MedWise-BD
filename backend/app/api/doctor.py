"""Doctor accounts for the Rx Pad (R2): sign up, log in, profile, chambers, password, data, delete.

Stored: only what app/models/doctor.py lists. Never patient information. Nothing personal is
logged (no request bodies, emails, passwords or tokens). Every response is Cache-Control: no-store
(app/core/security_headers.py). New accounts are "pending" until the owner verifies them with
scripts/doctors.py; there are no admin web pages.
"""

import time
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.frontend_auth import require_frontend
from app.core.rate_limit import RateLimiter, client_key, per_client_limit
from app.models import Doctor, DoctorChamber, DoctorPasswordReset, DoctorSession
from app.schemas.common import Envelope
from app.schemas.doctor import (
    ChamberOut,
    ChambersIn,
    DeleteIn,
    DoctorExport,
    DoctorOut,
    Done,
    LoginIn,
    PasswordChangeIn,
    PasswordResetIn,
    ProfileIn,
    SignupIn,
)
from app.schemas.rx import RxSignIn, RxSignOut
from app.services import rx_signing
from app.services.doctor_auth import (
    clear_session_cookie,
    client_guard,
    current_doctor,
    current_session,
    email_guard,
    end_sessions,
    require_same_site,
    set_session_cookie,
    start_session,
    token_hash,
    utcnow,
)
from app.services.passwords import (
    dummy_hash,
    hash_password,
    needs_rehash,
    password_problem,
    verify_password,
)

router = APIRouter(prefix="/doctor", tags=["doctor"], dependencies=[Depends(require_frontend)])

signup_limiter = RateLimiter(get_settings().doctor_signup_limit_per_hour, 3600)
rx_sign_limiter = RateLimiter(get_settings().rx_sign_limit_per_day, 86400)
CurrentDoctor = Annotated[Doctor, Depends(current_doctor)]
Db = Annotated[Session, Depends(get_db)]
SAME_SITE = [Depends(require_same_site)]

PASSWORD_MESSAGES = {
    "password_too_short": "Use at least 10 characters.",
    "password_too_long": "Use at most 128 characters.",
    "password_common": "This password is too common. Choose another one.",
    "password_personal": "Do not use your email or name as the password.",
}


def _check_password(password: str, email: str, name: str) -> None:
    problem = password_problem(password, email, name)
    if problem:
        raise AppError(422, problem, PASSWORD_MESSAGES[problem])


def doctor_out(doctor: Doctor) -> DoctorOut:
    return DoctorOut(
        email=doctor.email,
        display_name=doctor.display_name,
        display_name_bn=doctor.display_name_bn,
        degrees=doctor.degrees,
        specialty=doctor.specialty,
        bmdc_number=doctor.bmdc_number,
        phone=doctor.phone,
        status=doctor.status,  # type: ignore[arg-type]
        rejection_reason=doctor.rejection_reason,
        verified_on=doctor.verified_at.date() if doctor.verified_at else None,
        is_demo=doctor.is_demo,
        chambers=[
            ChamberOut(name=c.name, address=c.address, hours=c.hours, phone=c.phone)
            for c in doctor.chambers
        ],
    )


def back_to_pending(doctor: Doctor) -> None:
    """A changed name or BMDC number must be checked again: the badge would vouch for it."""
    doctor.status = "pending"
    doctor.rejection_reason = None
    doctor.verified_at = None
    doctor.verified_by = None
    doctor.verify_method = None


# ---------------------------------------------------------------- sign up, log in, log out


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[DoctorOut],
    dependencies=[*SAME_SITE, Depends(per_client_limit(signup_limiter))],
)
def signup(body: SignupIn, request: Request, response: Response, db: Db) -> Envelope[DoctorOut]:
    _check_password(body.password, body.email, body.display_name)
    if db.scalar(select(Doctor.id).where(Doctor.email == body.email)) is not None:
        raise AppError(
            409,
            "email_taken",
            "An account with this email already exists. Log in, or contact MedWise BD.",
        )
    doctor = Doctor(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        display_name_bn=body.display_name_bn,
        degrees=body.degrees,
        specialty=body.specialty,
        bmdc_number=body.bmdc_number,
        phone=body.phone,
        status="pending",
        is_demo=False,
        created_at=utcnow(),
    )
    db.add(doctor)
    db.flush()
    token = start_session(db, doctor)
    db.commit()
    set_session_cookie(response, request, token)
    return Envelope(data=doctor_out(doctor))


@router.post("/login", response_model=Envelope[DoctorOut], dependencies=SAME_SITE)
def login(body: LoginIn, request: Request, response: Response, db: Db) -> Envelope[DoctorOut]:
    email, client = body.email.strip().lower(), client_key(request)
    if email_guard.locked(email) or client_guard.locked(client):
        raise AppError(429, "login_locked", "Too many failed logins. Wait 15 minutes.")
    doctor = db.scalar(select(Doctor).where(Doctor.email == email))
    # Always verify a hash, so an unknown email takes as long as a wrong password.
    matches = verify_password(body.password, doctor.password_hash if doctor else dummy_hash())
    if doctor is None or not matches:
        email_guard.fail(email)
        client_guard.fail(client)
        raise AppError(401, "login_failed", "The email or password is not right.")
    email_guard.clear(email)
    if needs_rehash(doctor.password_hash):
        doctor.password_hash = hash_password(body.password)
    token = start_session(db, doctor)
    db.commit()
    set_session_cookie(response, request, token)
    return Envelope(data=doctor_out(doctor))


@router.post("/logout", response_model=Envelope[Done], dependencies=SAME_SITE)
def logout(
    request: Request,
    response: Response,
    db: Db,
    session: Annotated[DoctorSession, Depends(current_session)],
) -> Envelope[Done]:
    db.delete(session)
    db.commit()
    clear_session_cookie(response, request)
    return Envelope(data=Done())


@router.post("/logout-all", response_model=Envelope[Done], dependencies=SAME_SITE)
def logout_everywhere(
    request: Request, response: Response, db: Db, doctor: CurrentDoctor
) -> Envelope[Done]:
    end_sessions(db, doctor.id)
    db.commit()
    clear_session_cookie(response, request)
    return Envelope(data=Done())


# ---------------------------------------------------------------- profile and chambers


@router.get("/me", response_model=Envelope[DoctorOut])
def me(doctor: CurrentDoctor) -> Envelope[DoctorOut]:
    return Envelope(data=doctor_out(doctor))


@router.post("/profile", response_model=Envelope[DoctorOut], dependencies=SAME_SITE)
def update_profile(body: ProfileIn, db: Db, doctor: CurrentDoctor) -> Envelope[DoctorOut]:
    if (body.bmdc_number, body.display_name) != (doctor.bmdc_number, doctor.display_name):
        back_to_pending(doctor)
    for field, value in body.model_dump().items():
        setattr(doctor, field, value)
    db.commit()
    return Envelope(data=doctor_out(doctor))


@router.post("/chambers", response_model=Envelope[DoctorOut], dependencies=SAME_SITE)
def save_chambers(body: ChambersIn, db: Db, doctor: CurrentDoctor) -> Envelope[DoctorOut]:
    doctor.chambers.clear()
    db.flush()
    for position, chamber in enumerate(body.chambers):
        doctor.chambers.append(DoctorChamber(position=position, **chamber.model_dump()))
    db.commit()
    db.refresh(doctor)
    return Envelope(data=doctor_out(doctor))


# ---------------------------------------------------------------- password


@router.post("/password", response_model=Envelope[Done], dependencies=SAME_SITE)
def change_password(
    body: PasswordChangeIn,
    db: Db,
    doctor: CurrentDoctor,
    session: Annotated[DoctorSession, Depends(current_session)],
) -> Envelope[Done]:
    if not verify_password(body.current_password, doctor.password_hash):
        raise AppError(403, "wrong_password", "The current password is not right.")
    _check_password(body.new_password, doctor.email, doctor.display_name)
    doctor.password_hash = hash_password(body.new_password)
    end_sessions(db, doctor.id, keep=session.token_hash)  # other devices are logged out
    db.commit()
    return Envelope(data=Done())


@router.post(
    "/reset",
    response_model=Envelope[Done],
    dependencies=[*SAME_SITE, Depends(per_client_limit(signup_limiter))],
)
def reset_password(body: PasswordResetIn, db: Db) -> Envelope[Done]:
    """Use a one-time link from the owner (scripts/doctors.py reset-link)."""
    now = utcnow()
    reset = db.scalar(
        select(DoctorPasswordReset).where(DoctorPasswordReset.token_hash == token_hash(body.token))
    )
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        raise AppError(
            400, "reset_invalid", "This link has expired or was used. Ask MedWise BD for a new one."
        )
    doctor = db.get(Doctor, reset.doctor_id)
    if doctor is None:
        raise AppError(400, "reset_invalid", "This link has expired or was used.")
    _check_password(body.new_password, doctor.email, doctor.display_name)
    doctor.password_hash = hash_password(body.new_password)
    reset.used_at = now
    end_sessions(db, doctor.id)
    db.commit()
    return Envelope(data=Done())


# ---------------------------------------------------------------- your data


@router.get("/export", response_model=Envelope[DoctorExport])
def export_data(db: Db, doctor: CurrentDoctor) -> Envelope[DoctorExport]:
    sessions = db.scalar(
        select(func.count()).select_from(DoctorSession).where(DoctorSession.doctor_id == doctor.id)
    )
    return Envelope(
        data=DoctorExport(
            exported_on=date.today(),
            profile=doctor_out(doctor),
            created_on=doctor.created_at.date(),
            last_login_day=doctor.last_login_day,
            verified_by=doctor.verified_by,
            verify_method=doctor.verify_method,
            active_sessions=sessions or 0,
        )
    )


@router.post("/delete", response_model=Envelope[Done], dependencies=SAME_SITE)
def delete_account(
    body: DeleteIn, request: Request, response: Response, db: Db, doctor: CurrentDoctor
) -> Envelope[Done]:
    """Removes the profile, chambers, sessions and reset links (and, from R5, templates)."""
    if not verify_password(body.password, doctor.password_hash):
        raise AppError(403, "wrong_password", "The password is not right.")
    delete_doctor(db, doctor)
    db.commit()
    clear_session_cookie(response, request)
    return Envelope(data=Done())


# ---------------------------------------------------------------- Rx Pad QR (R4)


@router.post("/rx/sign", response_model=Envelope[RxSignOut], dependencies=SAME_SITE)
def sign_rx(body: RxSignIn, doctor: CurrentDoctor) -> Envelope[RxSignOut]:
    """Sign the hash of a prescription's QR payload. Only the hash reaches us; nothing is stored."""
    secret = get_settings().rx_signing_secret
    if not secret:
        raise AppError(503, "signing_unavailable", "QR codes are not set up yet.")
    if doctor.status == "rejected" and not doctor.is_demo:
        raise AppError(403, "not_allowed", "Your account was not verified.")
    if not rx_sign_limiter.allow(f"doctor:{doctor.id}"):
        raise AppError(429, "rate_limited", "Too many prescriptions today. Try again tomorrow.")
    issued_at = int(time.time())
    sig = rx_signing.sign(secret, doctor.id, issued_at, body.hash)
    return Envelope(data=RxSignOut(doctor_id=doctor.id, issued_at=issued_at, sig=sig))


def delete_doctor(db: Session, doctor: Doctor) -> None:
    """Delete a doctor and every row that belongs to them (also used by scripts/doctors.py)."""
    for model in (DoctorSession, DoctorPasswordReset, DoctorChamber):
        db.query(model).filter(model.doctor_id == doctor.id).delete()
    db.delete(doctor)
