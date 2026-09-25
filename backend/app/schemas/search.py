from typing import Literal

from pydantic import BaseModel


class SearchResult(BaseModel):
    type: Literal["brand", "generic"]
    id: int
    name: str
    score: float
    generic_id: int
    generic_name: str
    strength: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None


class SearchResponse(BaseModel):
    query: str
    interpreted_as: str
    results: list[SearchResult]
