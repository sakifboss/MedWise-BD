from typing import Literal

from pydantic import BaseModel, Field

FactorKey = Literal["certification", "export", "compliance", "recall_history", "market"]
UnknownKey = Literal["recall_history", "market_share", "export_country_count"]


class FactorDetail(BaseModel):
    key: FactorKey
    weight: float = Field(
        description="Weight of this factor in the quality score (weights sum to 1)"
    )
    score: float = Field(description="0-1, higher is better (recall history is already inverted)")
    points: float = Field(
        description="weight * score * 100: this factor's share of the 0-100 quality"
    )


class ManufacturerBrand(BaseModel):
    id: int
    code: str
    name: str
    generic_id: int
    generic_name: str
    strength: str
    dosage_form: str
    price_per_unit: float


class ManufacturerListItem(BaseModel):
    id: int
    name: str
    quality_score: float = Field(description="0-100")
    quality_rank: int
    stringent_approvals: list[str]
    brand_count: int


class ManufacturerDetail(BaseModel):
    id: int
    name: str
    years_active: int
    quality_score: float = Field(description="0-100, the manufacturer part of every brand's score")
    quality_rank: int
    manufacturer_count: int
    stringent_approvals: list[str]
    approvals_missing: list[str] = Field(
        description="Stringent regulators with no approved plant on record"
    )
    export_country_count: int | None = Field(
        description="None when the number of countries is unknown"
    )
    export_countries: list[str]
    regulated_market_exports: int
    compliance_score: float
    recall_data_available: bool
    recall_count: int
    market_share: float | None
    factors: list[FactorDetail]
    unknowns: list[UnknownKey] = Field(description="Facts we do not have for this manufacturer")
    source_urls: list[str]
    brands: list[ManufacturerBrand]
