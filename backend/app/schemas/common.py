from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class Envelope(BaseModel, Generic[T]):
    """Every API response has this shape: exactly one of data / error is set."""

    data: T | None = None
    error: ErrorBody | None = None
