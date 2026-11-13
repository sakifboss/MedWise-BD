"""Turn the team's filled-in brand sheet into data/seed/brands.json.

Fill data/templates/brands_template.csv (Excel or Google Sheets, then save as CSV),
then run from backend/:

    python scripts/build_brands_from_csv.py ../data/templates/brands_template.csv
    python scripts/import_data.py --dry-run

Each brand keeps its stable code (BR00042) from the current brands.json while its name,
manufacturer, strength and dosage form stay the same; new rows get the next unused code and
removed brands' codes are retired (scripts/brand_codes.py).

Rows with an empty brand_name are skipped (unused template rows). Every kept row needs a
manufacturer from manufacturers.json, a positive price and a price_source_url. If any row
is wrong, all problems are listed and brands.json is left untouched.
"""

import argparse
import csv
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.schemas.seed import normalize_strength  # noqa: E402
from scripts.brand_codes import assign_codes  # noqa: E402

REQUIRED_COLUMNS = (
    "brand_name",
    "generic",
    "strength",
    "dosage_form",
    "manufacturer",
    "price_per_unit",
    "price_source_url",
)


def _names(seed_dir: Path, dataset: str) -> dict[str, str]:
    doc = json.loads((seed_dir / f"{dataset}.json").read_text(encoding="utf-8"))
    return {r["name"].strip().casefold(): r["name"] for r in doc["records"]}


def _checked_on(value: str) -> dict[str, str]:
    """The day the price was checked, when the sheet has a valid date."""
    try:
        return {"price_checked_on": date.fromisoformat(value.strip()).isoformat()}
    except ValueError:
        return {}


def build_brands(csv_path: Path, seed_dir: Path) -> tuple[list[dict], list[str]]:
    """Return (brand records, errors). Records are only valid when errors is empty."""
    manufacturers = _names(seed_dir, "manufacturers")
    generics = _names(seed_dir, "generics")
    records: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [], [f"missing column(s): {', '.join(missing)}"]

        for line, row in enumerate(reader, start=2):
            cell = {k: (v or "").strip() for k, v in row.items() if k}
            if not cell["brand_name"]:
                continue
            where = f"line {line} ({cell['brand_name']})"

            generic = generics.get(cell["generic"].casefold())
            if generic is None:
                errors.append(f"{where}: unknown generic '{cell['generic']}'")
            manufacturer = manufacturers.get(cell["manufacturer"].casefold())
            if manufacturer is None:
                errors.append(
                    f"{where}: unknown manufacturer '{cell['manufacturer']}' "
                    f"(use one of: {', '.join(sorted(manufacturers.values()))})"
                )
            try:
                price = Decimal(cell["price_per_unit"])
                if price <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                errors.append(f"{where}: price_per_unit '{cell['price_per_unit']}' is not positive")
                price = Decimal(0)
            if not cell["price_source_url"].startswith(("http://", "https://")):
                errors.append(f"{where}: price_source_url must be a link")

            strength = normalize_strength(cell["strength"])
            form = cell["dosage_form"].lower()
            key = (cell["brand_name"].casefold(), cell["manufacturer"].casefold(), strength, form)
            if key in seen:
                errors.append(f"{where}: duplicate of an earlier row")
            seen.add(key)

            records.append(
                {
                    "name": cell["brand_name"],
                    "generic": generic or cell["generic"],
                    "manufacturer": manufacturer or cell["manufacturer"],
                    "strength": strength,
                    "dosage_form": form,
                    "price_per_unit": float(price),
                    "source_url": cell["price_source_url"],
                    **_checked_on(cell.get("date_checked", "")),
                }
            )
    return records, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="filled brands CSV")
    parser.add_argument("--seed-dir", type=Path, default=get_settings().seed_dir)
    args = parser.parse_args()

    records, errors = build_brands(args.csv, args.seed_dir)
    if errors:
        print(f"{len(errors)} problem(s); brands.json NOT written:")
        for error in errors:
            print(f"  - {error}")
        return 1
    if not records:
        print("No filled rows found; brands.json NOT written.")
        return 1

    out = args.seed_dir / "brands.json"
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    records, retired = assign_codes(records, previous)
    doc = {
        "meta": {
            "dataset": "brands",
            "source": "Collected by the MedWise BD team; each row's source_url is the price source",
            "is_sample": False,
            "note": f"Built from {args.csv.name} on {date.today().isoformat()}.",
            "retired_codes": retired,
        },
        "records": records,
    }
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    groups: dict[tuple[str, str, str], int] = {}
    for r in records:
        k = (r["generic"], r["strength"], r["dosage_form"])
        groups[k] = groups.get(k, 0) + 1
    print(f"Wrote {len(records)} brands to {out}")
    thin = [f"{g} {s} {f}" for (g, s, f), n in sorted(groups.items()) if n < 2]
    if thin:
        print("Only one brand (nothing to compare) for:", "; ".join(thin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
