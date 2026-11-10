"""List 'Report a problem' reports per brand, so the team can check and fix the seed files.

Reports are grouped by the brand's details saved with each report (brand ids change when the
seed import rebuilds the tables). There is no public endpoint for this; run it yourself:

    cd backend
    python scripts/top_reports.py          # uses DATABASE_URL from backend/.env
    python scripts/top_reports.py --database-url "postgresql://..." --days 30
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
from app.models import DataReport  # noqa: E402

REASON_LABELS = {
    "wrong_price": "wrong price",
    "not_sold": "not sold any more",
    "wrong_manufacturer": "wrong manufacturer",
    "other": "other",
}

Row = tuple[str, str, str, str, str, date]  # name, manufacturer, strength, form, reason, day
BrandKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class BrandReports:
    brand: str  # "Seclo 20 mg capsule (Square Pharmaceuticals PLC)"
    count: int
    reasons: dict[str, int]
    last_reported: date


def group_reports(rows: Iterable[Row], limit: int) -> list[BrandReports]:
    """Brands with the most reports first; ties by brand."""
    counts: Counter[BrandKey] = Counter()
    reasons: dict[BrandKey, Counter[str]] = {}
    last: dict[BrandKey, date] = {}
    for name, manufacturer, strength, form, reason, day in rows:
        key = (name, manufacturer, strength, form)
        counts[key] += 1
        reasons.setdefault(key, Counter())[reason] += 1
        last[key] = max(last.get(key, day), day)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [
        BrandReports(f"{k[0]} {k[2]} {k[3]} ({k[1]})", n, dict(reasons[k]), last[k])
        for k, n in ranked
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brands reported as having wrong data.")
    parser.add_argument("--database-url", default=get_settings().database_url)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--days", type=int, help="only the last N days")
    args = parser.parse_args(argv)

    engine = make_engine(args.database_url)
    if not inspect(engine).has_table(DataReport.__tablename__):
        print("No reports yet (the table is created by scripts/import_data.py).")
        engine.dispose()
        return 0
    stmt = select(
        DataReport.brand_name,
        DataReport.manufacturer,
        DataReport.strength,
        DataReport.dosage_form,
        DataReport.reason,
        DataReport.reported_on,
    )
    if args.days:
        since = datetime.now(UTC).date() - timedelta(days=args.days)
        stmt = stmt.where(DataReport.reported_on >= since)
    with Session(engine) as session:
        rows: list[Row] = [(a, b, c, d, e, f) for a, b, c, d, e, f in session.execute(stmt)]
    engine.dispose()

    top = group_reports(rows, args.limit)
    if not top:
        print("No reports yet.")
        return 0
    print(f"{len(rows)} reports in total. Brands with the most reports:\n")
    print(f"{'#':>3}  {'Count':>5}  {'Last':10}  Brand  (reasons)")
    for i, r in enumerate(top, start=1):
        reasons = ", ".join(f"{REASON_LABELS.get(k, k)} {n}" for k, n in sorted(r.reasons.items()))
        print(f"{i:>3}  {r.count:>5}  {r.last_reported.isoformat()}  {r.brand}  ({reasons})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
