"""Doctor accounts (R2). Only what the doctor types about themselves; never patient data."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import MAX_CHAMBERS

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")


def _email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL.match(value):
        raise ValueError("not a valid email address")
    return value


def _optional(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


Email = Annotated[str, AfterValidator(_email)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# BMDC registration numbers look like "A-12345" (MBBS) or "B-1234" (BDS); kept loose on purpose.
Bmdc = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{1,20}$")
]
Phone = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=20, pattern=r"^[0-9+\- ()]*$"),
    AfterValidator(_optional),
]
Password = Annotated[str, Field(max_length=128)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileIn(_In):
    display_name: Annotated[Text, Field(max_length=120)]
    display_name_bn: Annotated[str | None, Field(max_length=120), AfterValidator(_optional)] = None
    degrees: Annotated[Text, Field(max_length=200)]
    specialty: Annotated[Text, Field(max_length=120)]
    bmdc_number: Bmdc
    phone: Phone = None


class SignupIn(ProfileIn):
    email: Email
    password: Password


class LoginIn(_In):
    email: Annotated[str, Field(max_length=254)]
    password: Password


class ChamberIn(_In):
    name: Annotated[Text, Field(max_length=120)]
    address: Annotated[Text, Field(max_length=300)]
    hours: Annotated[Text, Field(max_length=200)]
    phone: Phone = None


class ChambersIn(_In):
    chambers: Annotated[list[ChamberIn], Field(max_length=MAX_CHAMBERS)]


class PasswordChangeIn(_In):
    current_password: Password
    new_password: Password


class PasswordResetIn(_In):
    token: Annotated[str, Field(min_length=20, max_length=100)]
    new_password: Password


class DeleteIn(_In):
    password: Password


class ChamberOut(BaseModel):
    name: str
    address: str
    hours: str
    phone: str | None


class DoctorOut(BaseModel):
    email: str
    display_name: str
    display_name_bn: str | None
    degrees: str
    specialty: str
    bmdc_number: str
    phone: str | None
    status: Literal["pending", "verified", "rejected"]
    rejection_reason: str | None
    verified_on: date | None
    is_demo: bool
    chambers: list[ChamberOut]


class DoctorExport(BaseModel):
    """Everything stored about the doctor (no password hash, no tokens)."""

    exported_on: date
    profile: DoctorOut
    created_on: date
    last_login_day: date | None
    verified_by: str | None
    verify_method: str | None
    active_sessions: int
    favourite_tests: list[str] = []
    templates: list[dict] = []
    note: str = (
        "This is everything MedWise BD stores about you. MedWise BD never stores your "
        "patients' information."
    )


class Done(BaseModel):
    ok: bool = True
