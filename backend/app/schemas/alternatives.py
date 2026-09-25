from pydantic import BaseModel

DISCLAIMER = "Consult your doctor or pharmacist before changing any medicine."


class GenericRef(BaseModel):
    id: int
    name: str


class ManufacturerSummary(BaseModel):
    id: int
    name: str
    who_gmp: bool


class QualityBreakdown(BaseModel):
    """Normalised 0-1 inputs to the quality score."""

    certification: float
    export: float
    compliance: float
    recall_history: float
    market: float


class RankedAlternative(BaseModel):
    rank: int
    brand_id: int
    name: str
    manufacturer: ManufacturerSummary
    price_per_unit: float
    final_score: float
    quality_score: float
    price_score: float
    quality_breakdown: QualityBreakdown
    reasons: list[str]
    is_selected: bool


class AlternativesResponse(BaseModel):
    selected_brand_id: int | None
    generic: GenericRef
    strength: str
    dosage_form: str
    alternatives: list[RankedAlternative]
    disclaimer: str = DISCLAIMER
