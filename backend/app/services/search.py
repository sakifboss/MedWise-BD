"""Fuzzy search over brand and generic names (Latin or Bangla input).

Matching runs in Python with rapidfuzz, which is fast enough for a national brand list
(tens of thousands of names). A Postgres pg_trgm prefilter can be added later if needed.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from rapidfuzz import fuzz, utils
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.catalog_cache import catalog_cache
from app.models import Brand, Generic, Manufacturer
from app.services.transliterate import phonetic_key, to_latin

MIN_SCORE = 70.0


@dataclass(frozen=True)
class SearchHit:
    type: Literal["brand", "generic"]
    id: int
    name: str
    score: float
    generic_id: int
    generic_name: str
    strength: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None
    code: str | None = None


@lru_cache(maxsize=4096)
def _name_key(name: str) -> str:
    return phonetic_key(name)


def match_score(latin_query: str, query_key: str, name: str) -> float:
    """Best of a plain fuzzy match and a phonetic-key match, 0-100."""
    plain = fuzz.WRatio(latin_query, name, processor=utils.default_process)
    phonetic = fuzz.WRatio(query_key, _name_key(name)) if query_key else 0.0
    return max(plain, phonetic)


@dataclass(frozen=True)
class _BrandName:
    id: int
    names: tuple[str, ...]  # the brand's name, then its aliases (other written names)
    strength: str
    dosage_form: str
    generic_id: int
    generic_name: str
    manufacturer: str
    code: str


@dataclass(frozen=True)
class _Names:
    generics: tuple[tuple[int, str], ...]
    brands: tuple[_BrandName, ...]


def _load_names(db: Session) -> _Names:
    generics = tuple((gid, name) for gid, name in db.execute(select(Generic.id, Generic.name)))
    rows = db.execute(
        select(
            Brand.id,
            Brand.name,
            Brand.aliases,
            Brand.strength,
            Brand.dosage_form,
            Generic.id,
            Generic.name,
            Manufacturer.name,
            Brand.code,
        )
        .join(Generic, Brand.generic_id == Generic.id)
        .join(Manufacturer, Brand.manufacturer_id == Manufacturer.id)
    )
    brands = tuple(
        _BrandName(bid, (name, *(aliases or [])), strength, form, gid, gname, maker, code)
        for bid, name, aliases, strength, form, gid, gname, maker, code in rows
    )
    return _Names(generics, brands)


def _names(db: Session) -> _Names:
    """Every generic and brand name, from memory after the first search (no database trip)."""
    return catalog_cache.get_or_build(("search-names",), lambda: _load_names(db))


def _generic_hits(names: _Names, latin: str, key: str) -> list[SearchHit]:
    hits = []
    for generic_id, name in names.generics:
        score = match_score(latin, key, name)
        if score >= MIN_SCORE:
            hits.append(SearchHit("generic", generic_id, name, score, generic_id, name))
    return hits


def _brand_hits(names: _Names, latin: str, key: str) -> list[SearchHit]:
    scores: dict[tuple[str, ...], float] = {}
    hits = []
    for b in names.brands:
        # A brand matches by its name or by any other name people write for it (seed aliases).
        if b.names not in scores:
            scores[b.names] = max(match_score(latin, key, n) for n in b.names)
        score = scores[b.names]
        if score >= MIN_SCORE:
            hits.append(
                SearchHit(
                    "brand",
                    b.id,
                    b.names[0],
                    score,
                    b.generic_id,
                    b.generic_name,
                    b.strength,
                    b.dosage_form,
                    b.manufacturer,
                    b.code,
                )
            )
    return hits


def search_catalog(db: Session, query: str, limit: int) -> tuple[str, list[SearchHit]]:
    """Return (query as interpreted in Latin script, best hits first)."""
    latin = to_latin(query).strip()
    key = phonetic_key(latin)
    if not utils.default_process(latin) and not key:
        return latin, []
    names = _names(db)
    hits = _generic_hits(names, latin, key) + _brand_hits(names, latin, key)
    hits.sort(key=lambda h: (-h.score, h.type != "generic", h.name.casefold(), h.strength or ""))
    return latin, hits[:limit]
