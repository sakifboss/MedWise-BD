from pydantic import BaseModel

DISCLAIMER = "Consult your doctor or pharmacist before changing any medicine."
DISCLAIMER_BN = "কোনো ওষুধ বদলানোর আগে আপনার ডাক্তার বা ফার্মাসিস্টের পরামর্শ নিন।"


class GenericRef(BaseModel):
    id: int
    name: str


class ManufacturerSummary(BaseModel):
    id: int
    name: str
    stringent_approvals: list[str]
    source_urls: list[str]


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
    # Stable across deploys: use it for links and anything saved (ids change on every import).
    code: str
    name: str
    manufacturer: ManufacturerSummary
    price_per_unit: float
    price_source_url: str | None
    final_score: float
    quality_score: float
    price_score: float
    quality_breakdown: QualityBreakdown
    reasons: list[str]
    is_selected: bool


class AlternativesResponse(BaseModel):
    selected_brand_id: int | None
    selected_brand_code: str | None
    generic: GenericRef
    strength: str
    dosage_form: str
    alternatives: list[RankedAlternative]
    disclaimer: str = DISCLAIMER
