from typing import Literal

from pydantic import BaseModel

PRIVACY_NOTE = (
    "Your photo was sent to OpenAI only to read medicine names and strengths. "
    "MedWise does not store it."
)


class MatchOptionOut(BaseModel):
    kind: Literal["brand", "generic"]
    brand_id: int | None
    generic_id: int
    generic_name: str
    name: str
    strength: str
    dosage_form: str
    manufacturer: str | None
    score: float
    strength_matches: bool


class PrescriptionItem(BaseModel):
    extracted_name: str
    extracted_strength: str | None
    options: list[MatchOptionOut]
    suggested_index: int | None


class PrescriptionResponse(BaseModel):
    items: list[PrescriptionItem]
    note: str = PRIVACY_NOTE
