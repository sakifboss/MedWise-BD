from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.medicine_request import QUERY_MAX_LENGTH


class MedicineRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500, description="What the person searched for")
    source: Literal["search", "prescription"]

    @field_validator("query")
    @classmethod
    def _trim(cls, value: str) -> str:
        """Collapse spaces and keep the first 80 characters; nothing else is stored."""
        cleaned = " ".join(value.split())[:QUERY_MAX_LENGTH].strip()
        if not cleaned:
            raise ValueError("query is empty")
        return cleaned


class MedicineRequestSaved(BaseModel):
    saved: bool = True


class CatalogStats(BaseModel):
    generics: int
    brands: int
    manufacturers: int
    interactions: int
