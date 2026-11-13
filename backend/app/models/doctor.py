"""Doctor accounts for the Rx Pad (R2). The only personal data MedWise BD stores.

Stored and nothing else: the doctor's email, password hash, profile, up to 3 chambers, sessions
(hashed tokens) and password-reset tokens (hashed). Never anything about patients. Durable tables
(RequestsBase): the seed import never drops them; they change only through Alembic migrations.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import RequestsBase

DOCTOR_STATUSES = ("pending", "verified", "rejected")
MAX_CHAMBERS = 3
MAX_TEMPLATES = 100
MAX_FAVOURITE_TESTS = 50


class Doctor(RequestsBase):
    __tablename__ = "doctors"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'verified', 'rejected')", name="ck_doctor_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # lowercased
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    display_name_bn: Mapped[str | None] = mapped_column(String(120), nullable=True)
    degrees: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(120))
    bmdc_number: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)  # printed, optional
    status: Mapped[str] = mapped_column(String(10), default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(10), nullable=True)  # owner initials
    verify_method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_login_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The doctor's own list of test names (R5), shown as chips in the tests box; null = none yet.
    favourite_tests: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    chambers: Mapped[list["DoctorChamber"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        order_by="DoctorChamber.position",
    )


class DoctorChamber(RequestsBase):
    __tablename__ = "doctor_chambers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(300))
    hours: Mapped[str] = mapped_column(String(200))  # days and hours, as the doctor writes them
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    doctor: Mapped[Doctor] = relationship(back_populates="chambers")


class DoctorSession(RequestsBase):
    """A login. Only the sha256 of the cookie's random token is stored."""

    __tablename__ = "doctor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class DoctorPasswordReset(RequestsBase):
    """A one-time reset link made by the owner (scripts/doctors.py). Stored hashed; 60 minutes."""

    __tablename__ = "doctor_password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DoctorTemplate(RequestsBase):
    """A doctor's own named template (R5): medicine lines, tests and advice. Never patient fields.
    Private to the doctor: not shared, listed for others, ranked or aggregated."""

    __tablename__ = "doctor_templates"
    __table_args__ = (UniqueConstraint("doctor_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    # Each line: brand code with a name snapshot, or generic + strength + form, or a free-text name;
    # plus pattern, unit, food, duration, substitution and the doctor's note.
    lines: Mapped[list[dict]] = mapped_column(JSON)
    tests: Mapped[str] = mapped_column(Text, default="")
    advice: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
