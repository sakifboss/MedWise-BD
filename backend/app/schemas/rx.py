"""Rx Pad QR signing and checking (R4). Only a hash of the medicine lines ever reaches us."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PayloadHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RxSignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hash: PayloadHash


class RxSignOut(BaseModel):
    doctor_id: int
    issued_at: int  # Unix seconds, set by the server
    sig: str


class RxVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doctor_id: Annotated[int, Field(ge=1)]
    issued_at: Annotated[int, Field(ge=0)]
    hash: PayloadHash
    sig: Annotated[str, StringConstraints(max_length=64)]


class RxDoctorPublic(BaseModel):
    """What a valid QR shows about who issued it (the same as the printed letterhead)."""

    display_name: str
    display_name_bn: str | None
    degrees: str
    specialty: str
    bmdc_number: str
    status: Literal["pending", "verified", "rejected"]
    is_demo: bool


class RxVerifyOut(BaseModel):
    valid: bool
    doctor: RxDoctorPublic | None = None
