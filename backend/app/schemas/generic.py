from typing import Literal

from pydantic import BaseModel, Field


class Presentation(BaseModel):
    strength: str
    dosage_form: str
    brand_count: int
    min_price: float
    max_price: float


class GenericListItem(BaseModel):
    """Every generic with its strengths and forms (used to save all pages for offline use)."""

    id: int
    name: str
    presentations: list[Presentation]


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
    how_to_take: list[str] = Field(
        default=[], description="What the source says about food, milk, alcohol and timing"
    )
    source_urls: list[str]
    translation_pending: list[str] = Field(
        default=[],
        description="For lang=bn: fields still shown in English because no reviewed Bangla exists",
    )
    presentations: list[Presentation]
    interactions: list[InteractionSummary]
    # When not empty, the catalog lists this generic only in these local forms (eye drops, cream,
    # ...): DDInter's interactions are for it taken by mouth or injection, so none are shown.
    interactions_not_shown_forms: list[str] = []
