"""Manage doctor accounts (Rx Pad). Run it yourself; there are no admin web pages.

    cd backend
    python scripts/doctors.py list [--status pending]       # DATABASE_URL from backend/.env
    python scripts/doctors.py --prod list                   # PROD_DATABASE_URL from backend/.env
    python scripts/doctors.py show 12
    python scripts/doctors.py verify 12                     # asks you to confirm each check
    python scripts/doctors.py reject 12 --reason "The BMDC number does not match the name."
    python scripts/doctors.py reset-link 12                 # one-time link, 60 minutes
    python scripts/doctors.py create-demo --email demo@example.com --name "Dr. Demo"
    python scripts/doctors.py delete 12

A doctor is given by id or email. Passwords and tokens are never printed, except a reset link or
a new demo password, once, for you to pass on.

Verification checks (no ID documents or photos are uploaded or stored):
1. Name and registration number match on the official BMDC register: https://www.bmdc.org.bd
   ("Find Registered MBBS / BDS Doctor": the number, then the captcha; it works only in a browser).
2. Identity confirmed in person, or by calling a chamber or hospital number you found yourself
   (not the number typed at sign-up).
"""

import argparse
import secrets
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.doctor import back_to_pending, delete_doctor  # noqa: E402
from app.core.config import BACKEND_DIR, get_settings  # noqa: E402
from app.core.db import make_engine  # noqa: E402
from app.models import Doctor, DoctorPasswordReset  # noqa: E402
from app.services.doctor_auth import RESET_VALID, new_token, utcnow  # noqa: E402
from app.services.passwords import hash_password  # noqa: E402

LIVE_SITE = "https://medwise-bd.vercel.app"

CHECKS = (
    "Name and BMDC registration number match on the official register "
    "(https://www.bmdc.org.bd, 'Find Registered MBBS / BDS Doctor')",
    "Identity confirmed in person, or through a chamber or hospital phone number I found myself "
    "(not the number typed at sign-up)",
)

Ask = Callable[[str], str]


class Stop(Exception):
    """A command could not run; the message says why."""


def find(db: Session, ref: str) -> Doctor:
    doctor = (
        db.get(Doctor, int(ref))
        if ref.isdigit()
        else db.scalar(select(Doctor).where(Doctor.email == ref.strip().lower()))
    )
    if doctor is None:
        raise Stop(f"No doctor {ref!r}.")
    return doctor


def describe(d: Doctor) -> str:
    demo = " DEMO" if d.is_demo else ""
    return (
        f"#{d.id} [{d.status}{demo}] {d.display_name} | BMDC {d.bmdc_number} | {d.specialty} | "
        f"{d.email} | joined {d.created_at.date()} | last login {d.last_login_day or '-'}"
    )


def cmd_list(db: Session, status: str | None) -> list[str]:
    query = select(Doctor).order_by(Doctor.created_at)
    if status:
        query = query.where(Doctor.status == status)
    return [describe(d) for d in db.scalars(query)] or ["No doctors."]


def cmd_show(db: Session, ref: str) -> list[str]:
    d = find(db, ref)
    lines = [
        describe(d),
        f"  name (bn): {d.display_name_bn or '-'} | degrees: {d.degrees} | phone: {d.phone or '-'}",
    ]
    if d.status == "verified":
        lines.append(f"  verified {d.verified_at:%Y-%m-%d} by {d.verified_by}: {d.verify_method}")
    if d.status == "rejected":
        lines.append(f"  rejected: {d.rejection_reason}")
    for i, c in enumerate(d.chambers, 1):
        lines.append(f"  chamber {i}: {c.name}, {c.address} | {c.hours} | {c.phone or '-'}")
    return lines


def cmd_verify(db: Session, ref: str, ask: Ask) -> list[str]:
    d = find(db, ref)
    if d.is_demo:
        raise Stop("Demo accounts are never verified.")
    print(describe(d))
    for number, check in enumerate(CHECKS, 1):
        if ask(f"Check {number}: {check}. Done? [y/N] ").strip().lower() not in ("y", "yes"):
            raise Stop("Not verified: every check must be confirmed.")
    initials = ask("Your initials: ").strip()[:10]
    method = ask("How identity was confirmed (e.g. 'called chamber, number from hospital site'): ")
    if not initials or not method.strip():
        raise Stop("Not verified: initials and method are required.")
    d.status, d.rejection_reason = "verified", None
    d.verified_at, d.verified_by, d.verify_method = utcnow(), initials, method.strip()[:200]
    db.commit()
    return [f"Verified: {describe(d)}"]


def cmd_reject(db: Session, ref: str, reason: str) -> list[str]:
    d = find(db, ref)
    if not reason.strip():
        raise Stop("Give a reason (the doctor sees it).")
    back_to_pending(d)
    d.status, d.rejection_reason = "rejected", reason.strip()[:300]
    db.commit()
    return [f"Rejected: {describe(d)}"]


def cmd_reset_link(db: Session, ref: str, site: str) -> list[str]:
    d = find(db, ref)
    token, hashed = new_token()
    db.add(
        DoctorPasswordReset(token_hash=hashed, doctor_id=d.id, expires_at=utcnow() + RESET_VALID)
    )
    db.commit()
    # The token goes after '#': browsers never send that part to any server, so it is not logged.
    return [
        f"Reset link for {d.display_name} (valid 60 minutes, works once). Send it only after "
        "confirming who they are by phone:",
        f"{site.rstrip('/')}/doctor/reset#{token}",
    ]


def cmd_create_demo(db: Session, email: str, name: str) -> list[str]:
    email = email.strip().lower()
    if db.scalar(select(Doctor.id).where(Doctor.email == email)) is not None:
        raise Stop(f"{email} already has an account.")
    password = secrets.token_urlsafe(12)
    d = Doctor(
        email=email,
        password_hash=hash_password(password),
        display_name=name.strip(),
        degrees="DEMO",
        specialty="DEMO",
        bmdc_number="DEMO",
        status="pending",
        is_demo=True,
        created_at=utcnow(),
    )
    db.add(d)
    db.commit()
    return [f"Demo account: {describe(d)}", f"Password (shown once): {password}"]


def cmd_delete(db: Session, ref: str, ask: Ask) -> list[str]:
    d = find(db, ref)
    print(describe(d))
    if ask(f"Type the email ({d.email}) to delete this account and everything in it: ").strip() != (
        d.email
    ):
        raise Stop("Not deleted.")
    delete_doctor(db, d)
    db.commit()
    return ["Deleted."]


def _prod_url() -> str:
    for line in (BACKEND_DIR / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("PROD_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise Stop("PROD_DATABASE_URL is not in backend/.env")


def _ask(prompt: str) -> str:
    """input(), with no input (closed stdin) taken as "no"."""
    try:
        return input(prompt)
    except EOFError:
        print()
        return ""


def main(argv: list[str] | None = None, ask: Ask = _ask) -> int:
    parser = argparse.ArgumentParser(description="Manage doctor accounts.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--prod", action="store_true", help="use PROD_DATABASE_URL from .env")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").add_argument("--status", choices=("pending", "verified", "rejected"))
    for name in ("show", "verify", "delete"):
        sub.add_parser(name).add_argument("doctor")
    reject = sub.add_parser("reject")
    reject.add_argument("doctor")
    reject.add_argument("--reason", required=True)
    reset = sub.add_parser("reset-link")
    reset.add_argument("doctor")
    reset.add_argument("--site", default=LIVE_SITE)
    demo = sub.add_parser("create-demo")
    demo.add_argument("--email", required=True)
    demo.add_argument("--name", required=True)
    args = parser.parse_args(argv)

    try:
        url = _prod_url() if args.prod else (args.database_url or get_settings().database_url)
        engine = make_engine(url)
        with Session(engine) as db:
            commands: dict[str, Callable[[], list[str]]] = {
                "list": lambda: cmd_list(db, args.status),
                "show": lambda: cmd_show(db, args.doctor),
                "verify": lambda: cmd_verify(db, args.doctor, ask),
                "reject": lambda: cmd_reject(db, args.doctor, args.reason),
                "reset-link": lambda: cmd_reset_link(db, args.doctor, args.site),
                "create-demo": lambda: cmd_create_demo(db, args.email, args.name),
                "delete": lambda: cmd_delete(db, args.doctor, ask),
            }
            lines = commands[args.command]()
        engine.dispose()
    except Stop as stop:
        print(stop)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
