"""Small in-memory sliding-window rate limiter.

State lives in the process, so it resets on restart and is per instance. That is enough
for a single free-tier instance; use Redis if the backend is ever scaled out.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request


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
    """Best-effort client identity.

    Requests reach us through proxies (Vercel's rewrite, Render's load balancer), which put
    the original client first in X-Forwarded-For. A client can spoof that header, so the
    per-client limit is a courtesy; the global daily limit is the hard protection.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"
