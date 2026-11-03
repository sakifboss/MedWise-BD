from typing import Annotated, Any, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

Lang = Literal["en", "bn"]
LangQuery = Annotated[Lang, Query(description="Language for generated text: en (default) or bn")]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class Envelope(BaseModel, Generic[T]):
    """Every API response has this shape: exactly one of data / error is set."""

    data: T | None = None
    error: ErrorBody | None = None
