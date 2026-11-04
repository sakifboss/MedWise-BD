"""Small in-memory sliding-window rate limiter.

State lives in the process, so it resets on restart and is per instance. That is enough
for a single free-tier instance; use Redis if the backend is ever scaled out.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.errors import AppError
from app.core.frontend_auth import came_from_frontend


class RateLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key` and return False if it is over the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    """Client identity for rate limits.

    Our frontend's requests reach us through Vercel, which overwrites X-Forwarded-For with the
    real client address, so its first entry is trustworthy for them (they carry the shared
    secret). Anyone else could put any address there, so for other requests only the last entry,
    added by our own hosting proxy, is used.
    """
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if hops:
        return hops[0] if came_from_frontend(request) else hops[-1]
    return request.client.host if request.client else "unknown"


def per_client_limit(limiter: RateLimiter) -> Callable[[Request], None]:
    """FastAPI dependency that answers 429 once a client goes over `limiter`."""

    def dependency(request: Request) -> None:
        if not limiter.allow(client_key(request)):
            raise AppError(
                429, "rate_limited", "Too many requests in a short time. Please wait a minute."
            )

    return dependency
