import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import alternatives, generics, interactions, prescription, search
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.schemas.common import Envelope, ErrorBody

logger = logging.getLogger(__name__)

_ERROR_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body = Envelope[None](error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump())


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _ERROR_CODES.get(exc.status_code, "http_error")
    return _error(exc.status_code, code, str(exc.detail))


async def _app_error(_: Request, exc: AppError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message)


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
    ]
    return _error(422, "validation_error", "Invalid request parameters", details)


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return _error(500, "internal_error", "Something went wrong. Please try again.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MedWise BD API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, _app_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error)

    for module in (search, generics, alternatives, prescription, interactions):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health", response_model=Envelope[dict[str, str]], tags=["health"])
    def health(db: Annotated[Session, Depends(get_db)]) -> Envelope[dict[str, str]]:
        db.execute(text("SELECT 1"))
        return Envelope(data={"status": "ok", "database": "ok"})

    return app


app = create_app()
