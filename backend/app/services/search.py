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


@lru_cache(maxsize=4096)
def _name_key(name: str) -> str:
    return phonetic_key(name)


def match_score(latin_query: str, query_key: str, name: str) -> float:
    """Best of a plain fuzzy match and a phonetic-key match, 0-100."""
    plain = fuzz.WRatio(latin_query, name, processor=utils.default_process)
    phonetic = fuzz.WRatio(query_key, _name_key(name)) if query_key else 0.0
    return max(plain, phonetic)


def _generic_hits(db: Session, latin: str, key: str) -> list[SearchHit]:
    hits = []
    for generic_id, name in db.execute(select(Generic.id, Generic.name)):
        score = match_score(latin, key, name)
        if score >= MIN_SCORE:
            hits.append(SearchHit("generic", generic_id, name, score, generic_id, name))
    return hits


def _brand_hits(db: Session, latin: str, key: str) -> list[SearchHit]:
    rows = db.execute(
        select(
            Brand.id,
            Brand.name,
            Brand.strength,
            Brand.dosage_form,
            Generic.id,
            Generic.name,
            Manufacturer.name,
        )
        .join(Generic, Brand.generic_id == Generic.id)
        .join(Manufacturer, Brand.manufacturer_id == Manufacturer.id)
    )
    scores: dict[str, float] = {}
    hits = []
    for brand_id, name, strength, form, generic_id, generic_name, manufacturer in rows:
        if name not in scores:
            scores[name] = match_score(latin, key, name)
        if scores[name] >= MIN_SCORE:
            hits.append(
                SearchHit(
                    "brand",
                    brand_id,
                    name,
                    scores[name],
                    generic_id,
                    generic_name,
                    strength,
                    form,
                    manufacturer,
                )
            )
    return hits


def search_catalog(db: Session, query: str, limit: int) -> tuple[str, list[SearchHit]]:
    """Return (query as interpreted in Latin script, best hits first)."""
    latin = to_latin(query).strip()
    key = phonetic_key(latin)
    if not utils.default_process(latin) and not key:
        return latin, []
    hits = _generic_hits(db, latin, key) + _brand_hits(db, latin, key)
    hits.sort(key=lambda h: (-h.score, h.type != "generic", h.name.casefold(), h.strength or ""))
    return latin, hits[:limit]
