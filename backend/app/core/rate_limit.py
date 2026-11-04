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


# Set by the hosting layer itself; clients cannot forge them (checked on the live site: Vercel
# replaces a forged value, Cloudflare in front of Render rejects requests that send one).
VERCEL_CLIENT_IP = "x-vercel-forwarded-for"  # on requests our frontend proxies to us
CLOUDFLARE_CLIENT_IP = "cf-connecting-ip"  # on every request that reaches Render


def _first(value: str | None) -> str | None:
    first = (value or "").split(",")[0].strip()
    return first or None


def client_key(request: Request) -> str:
    """Client address for rate limits, taken only from headers a client cannot forge.

    X-Forwarded-For is not used in production: anyone can put any address in it, and Vercel
    passes a client's value through to us. It is only the fallback for local runs (dev server,
    Docker, tests), where neither Vercel nor Cloudflare is in front.
    """
    trusted = (
        request.headers.get(VERCEL_CLIENT_IP) if came_from_frontend(request) else None
    ) or request.headers.get(CLOUDFLARE_CLIENT_IP)
    address = _first(trusted) or _first(request.headers.get("x-forwarded-for"))
    if address:
        return address
    return request.client.host if request.client else "unknown"


def per_client_limit(limiter: RateLimiter) -> Callable[[Request], None]:
    """FastAPI dependency that answers 429 once a client goes over `limiter`."""

    def dependency(request: Request) -> None:
        if not limiter.allow(client_key(request)):
            raise AppError(
                429, "rate_limited", "Too many requests in a short time. Please wait a minute."
            )

    return dependency
