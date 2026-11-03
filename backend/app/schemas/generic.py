from typing import Literal

from pydantic import BaseModel


class Presentation(BaseModel):
    strength: str
    dosage_form: str
    brand_count: int
    min_price: float
    max_price: float


class InteractionSummary(BaseModel):
    generic_id: int
    generic_name: str
    severity: Literal["minor", "moderate", "major"]
    description: str


class GenericDetail(BaseModel):
    id: int
    name: str
    drug_class: str
    indications: list[str]
    dosage_forms: list[str]
    side_effects: list[str]
    precautions: list[str]
    source_urls: list[str]
    presentations: list[Presentation]
    interactions: list[InteractionSummary]
