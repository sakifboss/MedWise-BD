"""Bangla medicine information through a review sheet (data/templates/generics_bn.csv).

The sheet has one row per line of English text (drug class, uses, side effects, precautions,
how to take) with its Bangla translation and an `approved` column. From backend/:

    # Add rows for new or changed English text (keeps every existing translation):
    python scripts/build_generics_bn.py export ../data/templates/generics_bn.csv

    # After review, copy approved translations into data/seed/generics.json:
    python scripts/build_generics_bn.py apply ../data/templates/generics_bn.csv
    python scripts/import_data.py --dry-run

A field is shown in Bangla only when EVERY line of it is approved, so a list is never half
English, half Bangla. If a row's English no longer matches generics.json (the source text
changed), the row is reported as stale and nothing is written.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.schemas.seed import TRANSLATED_FIELDS  # noqa: E402

COLUMNS = ("generic", "field", "line", "english", "bangla", "approved", "reviewed_by", "notes")
APPROVED = {"yes", "y", "true", "1", "approved", "হ্যাঁ", "হ্যা"}

Key = tuple[str, str, int]


def _english_lines(record: dict) -> dict[str, list[str]]:
    return {
        f: [record[f]] if f == "drug_class" else list(record.get(f, [])) for f in TRANSLATED_FIELDS
    }


def _load_generics(seed_dir: Path) -> dict:
    return json.loads((seed_dir / "generics.json").read_text(encoding="utf-8"))


def read_sheet(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(handle)
        ]


def export_sheet(sheet: Path, seed_dir: Path) -> int:
    """Write one row per English line, keeping translations whose English is unchanged."""
    kept = {(r["generic"], r["field"], r["english"]): r for r in read_sheet(sheet)}
    rows = []
    for record in _load_generics(seed_dir)["records"]:
        for field, lines in _english_lines(record).items():
            for number, english in enumerate(lines, start=1):
                old = kept.get((record["name"], field, english), {})
                rows.append(
                    {
                        "generic": record["name"],
                        "field": field,
                        "line": str(number),
                        "english": english,
                        "bangla": old.get("bangla", ""),
                        "approved": old.get("approved", ""),
                        "reviewed_by": old.get("reviewed_by", ""),
                        "notes": old.get("notes", ""),
                    }
                )
    sheet.parent.mkdir(parents=True, exist_ok=True)
    with sheet.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def apply_sheet(sheet: Path, seed_dir: Path) -> tuple[dict, list[str], dict[str, tuple[int, int]]]:
    """Return (updated generics doc, errors, {field: (approved fields, total fields)})."""
    doc = _load_generics(seed_dir)
    english = {r["name"]: _english_lines(r) for r in doc["records"]}
    approved: dict[Key, str] = {}
    errors: list[str] = []

    for line_no, row in enumerate(read_sheet(sheet), start=2):
        generic, field = row.get("generic", ""), row.get("field", "")
        where = f"line {line_no} ({generic} {field} {row.get('line', '')})"
        if generic not in english:
            errors.append(f"{where}: unknown generic '{generic}'")
            continue
        if field not in TRANSLATED_FIELDS:
            errors.append(f"{where}: field must be one of {', '.join(TRANSLATED_FIELDS)}")
            continue
        try:
            number = int(row.get("line", ""))
            current = english[generic][field][number - 1]
        except (ValueError, IndexError):
            errors.append(f"{where}: no such line in generics.json")
            continue
        if row.get("english", "") != current:
            errors.append(f"{where}: stale, the English text changed; run 'export' and re-review")
            continue
        if row.get("approved", "").casefold() in APPROVED:
            if not row.get("bangla"):
                errors.append(f"{where}: approved but the Bangla column is empty")
                continue
            approved[(generic, field, number)] = row["bangla"]

    coverage = {field: [0, 0] for field in TRANSLATED_FIELDS}
    for record in doc["records"]:
        for field, lines in english[record["name"]].items():
            if not lines:
                continue
            coverage[field][1] += 1
            bangla = [approved.get((record["name"], field, n)) for n in range(1, len(lines) + 1)]
            key = f"{field}_bn"
            if all(bangla):
                coverage[field][0] += 1
                record[key] = bangla[0] if field == "drug_class" else bangla
            else:
                record.pop(key, None)  # incomplete: keep showing English
    return doc, errors, {f: (a, t) for f, (a, t) in coverage.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["export", "apply"])
    parser.add_argument("sheet", type=Path, help="review sheet CSV")
    parser.add_argument("--seed-dir", type=Path, default=get_settings().seed_dir)
    args = parser.parse_args()

    if args.command == "export":
        count = export_sheet(args.sheet, args.seed_dir)
        print(f"Wrote {count} rows to {args.sheet}")
        return 0

    doc, errors, coverage = apply_sheet(args.sheet, args.seed_dir)
    if errors:
        print(f"{len(errors)} problem(s); generics.json NOT written:")
        for error in errors:
            print(f"  - {error}")
        return 1
    out = args.seed_dir / "generics.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {out}. Fields now shown in Bangla (fully approved):")
    for field, (done, total) in coverage.items():
        print(f"  {field:13} {done}/{total} generics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
