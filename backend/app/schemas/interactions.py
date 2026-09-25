from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.alternatives import DISCLAIMER

NO_RECORD_NOTE = (
    "Only interactions recorded in our data are shown. No result does not mean it is safe to "
    "combine medicines."
)


class InteractionCheckRequest(BaseModel):
    brand_ids: list[int] = Field(default=[], max_length=20)
    generic_ids: list[int] = Field(default=[], max_length=20)

    @model_validator(mode="after")
    def _not_empty(self) -> "InteractionCheckRequest":
        if not self.brand_ids and not self.generic_ids:
            raise ValueError("provide at least one brand_id or generic_id")
        return self


class CheckedMedicine(BaseModel):
    generic_id: int
    generic_name: str
    brands: list[str]


class GenericRef(BaseModel):
    id: int
    name: str


class InteractionOut(BaseModel):
    generic_a: GenericRef
    generic_b: GenericRef
    severity: Literal["minor", "moderate", "major"]
    description: str


class InteractionCheckResponse(BaseModel):
    medicines: list[CheckedMedicine]
    interactions: list[InteractionOut]
    duplicates: list[CheckedMedicine]
    pairs_checked: int
    note: str = NO_RECORD_NOTE
    disclaimer: str = DISCLAIMER
