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


def require_frontend(request: Request) -> None:
    secret = get_settings().frontend_shared_secret
    if not secret:
        return
    sent = request.headers.get(FRONTEND_SECRET_HEADER, "")
    # Constant-time comparison, so response timing reveals nothing about the secret.
    if not hmac.compare_digest(sent.encode(), secret.encode()):
        raise AppError(
            403,
            "forbidden",
            "Prescription reading is only available through the MedWise BD website.",
        )
