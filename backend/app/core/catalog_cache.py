"""In-memory cache for answers built only from the seed tables (the medicine catalog).

The catalog changes only when import_data.py runs, which happens before the server starts on
every deploy, so a cached answer stays right for the life of the process. Every entry still
expires after `catalog_cache_seconds` (a safety net, e.g. for an import run by hand against a
running local server), and run_import() clears the cache when it runs in the same process.

Never used for anything people send us (requests, reports, doctor data) or for answers that
depend on who is asking. Errors (e.g. 404) are not cached: only returned values are stored.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from app.core.config import get_settings

T = TypeVar("T")

MAX_ENTRIES = 2000  # about 4 per brand; least recently used first out


class CatalogCache:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._max = max_entries
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_build(self, key: Hashable, build: Callable[[], T]) -> T:
        ttl = get_settings().catalog_cache_seconds
        if ttl <= 0:
            return build()
        now = time.monotonic()
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and hit[0] > now:
                self._entries.move_to_end(key)
                return hit[1]  # type: ignore[no-any-return]
        # Built outside the lock: two requests may build the same answer once; both are correct.
        value = build()
        with self._lock:
            self._entries[key] = (now + ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


catalog_cache = CatalogCache()
