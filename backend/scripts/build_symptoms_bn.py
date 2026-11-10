"""Bangla for the symptom guide through a review sheet (data/templates/symptoms_bn.csv).

One row per English text: every emergency sign in red_flags.json (NHS wording) and every
specialty name and description in specialties.json. A Bangla speaker checks each row and writes
`yes` in `approved`. From backend/:

    # Add rows for new or changed English text (keeps every existing translation):
    python scripts/build_symptoms_bn.py export ../data/templates/symptoms_bn.csv

    # After review, copy approved translations into data/seed/*.json:
    python scripts/build_symptoms_bn.py apply ../data/templates/symptoms_bn.csv
    python scripts/import_data.py --dry-run

Only approved rows are applied; anything else keeps the English. If a row's English no longer
matches the seed file (the source text changed), it is reported as stale and nothing is written.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402

COLUMNS = ("dataset", "id", "field", "english", "bangla", "approved", "reviewed_by", "notes")
APPROVED = {"yes", "y", "true", "1", "approved", "হ্যাঁ", "হ্যা"}
# dataset -> fields with a Bangla twin (`<field>_bn`)
FIELDS = {"red_flags": ("text",), "specialties": ("name", "covers")}

Key = tuple[str, str, str]


def _load(seed_dir: Path, dataset: str) -> dict:
    return json.loads((seed_dir / f"{dataset}.json").read_text(encoding="utf-8"))


def _english(seed_dir: Path) -> dict[Key, str]:
    out: dict[Key, str] = {}
    for dataset, fields in FIELDS.items():
        for record in _load(seed_dir, dataset)["records"]:
            for f in fields:
                out[(dataset, record["id"], f)] = record[f]
    return out


def read_sheet(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {k: (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(handle)
        ]


def write_sheet(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c, "") for c in COLUMNS} for row in rows)


def export_sheet(sheet: Path, seed_dir: Path) -> int:
    """One row per English text, keeping rows whose English is unchanged."""
    kept = {(r["dataset"], r["id"], r["field"], r["english"]): r for r in read_sheet(sheet)}
    rows = []
    for (dataset, key, f), english in _english(seed_dir).items():
        old = kept.get((dataset, key, f, english))
        rows.append(old or {"dataset": dataset, "id": key, "field": f, "english": english})
    write_sheet(sheet, rows)
    return len(rows)


def apply_sheet(sheet: Path, seed_dir: Path) -> tuple[dict[str, dict], list[str], int]:
    """Approved Bangla per seed file. Returns (updated docs, problems, applied count)."""
    english = _english(seed_dir)
    problems: list[str] = []
    approved: dict[Key, str] = {}
    for n, row in enumerate(read_sheet(sheet), start=2):
        key = (row.get("dataset", ""), row.get("id", ""), row.get("field", ""))
        if key not in english:
            problems.append(f"row {n}: unknown {key}")
        elif row.get("english") != english[key]:
            problems.append(f"row {n}: stale (the English of {key} changed); export again")
        elif row.get("approved", "").casefold() in APPROVED:
            if not row.get("bangla"):
                problems.append(f"row {n}: approved but the Bangla is empty")
            else:
                approved[key] = row["bangla"]
    docs = {dataset: _load(seed_dir, dataset) for dataset in FIELDS}
    for dataset, fields in FIELDS.items():
        for record in docs[dataset]["records"]:
            for f in fields:
                record[f"{f}_bn"] = approved.get((dataset, record["id"], f))
    return docs, problems, len(approved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=("export", "apply"))
    parser.add_argument("sheet", type=Path)
    parser.add_argument("--seed-dir", type=Path, default=get_settings().seed_dir)
    args = parser.parse_args()

    if args.action == "export":
        print(f"Wrote {export_sheet(args.sheet, args.seed_dir)} rows to {args.sheet}")
        return 0
    docs, problems, applied = apply_sheet(args.sheet, args.seed_dir)
    if problems:
        print("Nothing written:")
        for p in problems:
            print(f"  - {p}")
        return 1
    for dataset, doc in docs.items():
        path = args.seed_dir / f"{dataset}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = len(_english(args.seed_dir))
    print(f"Applied {applied} of {total} Bangla texts; the rest stay in English.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
