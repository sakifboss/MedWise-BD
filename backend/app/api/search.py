from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import RateLimiter, per_client_limit
from app.schemas.common import Envelope
from app.schemas.search import SearchResponse, SearchResult
from app.services.search import search_catalog

router = APIRouter(tags=["search"])

search_limiter = RateLimiter(get_settings().search_limit_per_minute, 60)


@router.get(
    "/search",
    response_model=Envelope[SearchResponse],
    dependencies=[Depends(per_client_limit(search_limiter))],
)
def search(
    q: Annotated[str, Query(min_length=1, max_length=100, description="Brand or generic name")],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Envelope[SearchResponse]:
    interpreted_as, hits = search_catalog(db, q, limit)
    results = [SearchResult(**{**hit.__dict__, "score": round(hit.score, 1)}) for hit in hits]
    return Envelope(data=SearchResponse(query=q, interpreted_as=interpreted_as, results=results))
