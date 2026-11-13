"""Security headers for every API response.

The API only returns JSON, so its Content-Security-Policy forbids loading anything at all. The
interactive docs (/docs, /redoc) load Swagger/ReDoc assets from a CDN and keep FastAPI's defaults.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

DOCS_PATHS = ("/docs", "/redoc")
# Doctor accounts: never kept by the browser, the service worker or any cache in between.
NO_STORE_PATHS = ("/api/doctor",)

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def security_headers_for(path: str) -> dict[str, str]:
    if path.startswith(DOCS_PATHS):
        return COMMON_HEADERS
    return {**COMMON_HEADERS, "Content-Security-Policy": API_CSP}


def add_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for key, value in security_headers_for(request.url.path).items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith(NO_STORE_PATHS):
            response.headers["Cache-Control"] = "no-store"
        return response
