"""Print the most requested medicines from the 'Request this medicine' log.

Queries are grouped ignoring case and spaces ("napa", "Napa ", "NAPA" count together) and shown
as the spelling people used most. There is no public endpoint for this; run it yourself:

    cd backend
    python scripts/top_requests.py          # uses DATABASE_URL from backend/.env
    python scripts/top_requests.py --database-url "postgresql://..." --limit 50 --days 30
"""

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import make_engine  # noqa: E402
from app.models import MedicineRequest  # noqa: E402


@dataclass(frozen=True)
class TopRequest:
    query: str  # the spelling used most often
    count: int
    sources: dict[str, int]
    last_requested: date


def group_requests(rows: Iterable[tuple[str, str, date]], limit: int) -> list[TopRequest]:
    """rows: (query, source, requested_on). Most requested first; ties by name."""
    counts: Counter[str] = Counter()
    spellings: dict[str, Counter[str]] = {}
    sources: dict[str, Counter[str]] = {}
    last: dict[str, date] = {}
    for query, source, day in rows:
        key = " ".join(query.casefold().split())
        counts[key] += 1
        spellings.setdefault(key, Counter())[query.strip()] += 1
        sources.setdefault(key, Counter())[source] += 1
        last[key] = max(last.get(key, day), day)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [
        TopRequest(spellings[k].most_common(1)[0][0], n, dict(sources[k]), last[k])
        for k, n in ranked
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Most requested medicines.")
    parser.add_argument("--database-url", default=get_settings().database_url)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--days", type=int, help="only the last N days")
    args = parser.parse_args(argv)

    engine = make_engine(args.database_url)
    if not inspect(engine).has_table(MedicineRequest.__tablename__):
        print("No requests yet (the table is created by scripts/import_data.py).")
        return 0
    stmt = select(MedicineRequest.query, MedicineRequest.source, MedicineRequest.requested_on)
    if args.days:
        since = datetime.now(UTC).date() - timedelta(days=args.days)
        stmt = stmt.where(MedicineRequest.requested_on >= since)
    with Session(engine) as session:
        rows = [(q, s, d) for q, s, d in session.execute(stmt)]
    engine.dispose()

    top = group_requests(rows, args.limit)
    if not top:
        print("No requests yet.")
        return 0
    print(f"{len(rows)} requests in total. Top {len(top)}:\n")
    print(f"{'#':>3}  {'Count':>5}  {'Last':10}  Query  (sources)")
    for i, t in enumerate(top, start=1):
        where = ", ".join(f"{s} {n}" for s, n in sorted(t.sources.items()))
        print(f"{i:>3}  {t.count:>5}  {t.last_requested.isoformat()}  {t.query}  ({where})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
