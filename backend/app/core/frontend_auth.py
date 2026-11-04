"""Proof that a request came through our own frontend.

The Next.js proxy adds FRONTEND_SECRET_HEADER with the shared secret to prescription uploads, so
calling the backend directly cannot use up the Gemini quota. With no secret configured (local
development, tests) every request is allowed.
"""

import hmac

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

FRONTEND_SECRET_HEADER = "X-MedWise-Frontend"


def came_from_frontend(request: Request) -> bool:
    """True when the request carries the shared secret (or no secret is configured)."""
    secret = get_settings().frontend_shared_secret
    if not secret:
        return True
    sent = request.headers.get(FRONTEND_SECRET_HEADER, "")
    # Constant-time comparison, so response timing reveals nothing about the secret.
    return hmac.compare_digest(sent.encode(), secret.encode())


def require_frontend(request: Request) -> None:
    if not came_from_frontend(request):
        raise AppError(
            403,
            "forbidden",
            "Prescription reading is only available through the MedWise BD website.",
        )
