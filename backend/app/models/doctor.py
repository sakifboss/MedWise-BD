"""Doctor accounts for the Rx Pad (R2). The only personal data MedWise BD stores.

Stored and nothing else: the doctor's email, password hash, profile, up to 3 chambers, sessions
(hashed tokens) and password-reset tokens (hashed). Never anything about patients. Durable tables
(RequestsBase): the seed import never drops them; they change only through Alembic migrations.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import RequestsBase

DOCTOR_STATUSES = ("pending", "verified", "rejected")
MAX_CHAMBERS = 3


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
