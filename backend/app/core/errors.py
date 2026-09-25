from typing import Any


class AppError(Exception):
    """An expected error with a stable machine-readable code, returned in the error envelope."""

    def __init__(
        self, status: int, code: str, message: str, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
