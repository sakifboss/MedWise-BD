"""Build data/seed/interactions.json from the DDInter downloads (real interaction data).

1. In a browser, open https://ddinter.scbdd.com/download/ and download every
   ddinter_downloads_code_*.csv file into one folder, e.g. data/raw/ddinter/
2. From backend/ run:
       python scripts/extract_ddinter.py ../data/raw/ddinter
       python scripts/import_data.py --dry-run

Only pairs where BOTH medicines are generics in generics.json are kept. DDInter rows
with level "Unknown" are skipped; if a pair appears more than once, the most severe
level wins.

DDInter data is licensed CC BY-NC-SA 4.0 (non-commercial, attribution required).
Credit DDInter wherever interaction results are shown.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402

# Generic name in generics.json -> name(s) DDInter uses, where they differ.
DDINTER_ALIASES: dict[str, list[str]] = {
    "Paracetamol": ["Acetaminophen"],
    "Aspirin": ["Acetylsalicylic acid", "Aspirin"],
}

SEVERITY_RANK = {"minor": 1, "moderate": 2, "major": 3}

DESCRIPTIONS = {
    "major": (
        "DDInter lists this as a major interaction. Do not take these together unless a "
        "doctor has said it is safe."
    ),
    "moderate": (
        "DDInter lists this as a moderate interaction. Ask a doctor or pharmacist before "
        "taking these together; extra monitoring or a dose change may be needed."
    ),
    "minor": (
        "DDInter lists this as a minor interaction. Tell your doctor or pharmacist that you "
        "take both."
    ),
}

DESCRIPTIONS_BN = {
    "major": (
        "DDInter অনুযায়ী এটি একটি গুরুতর ইন্টারঅ্যাকশন। ডাক্তার নিরাপদ বলে না জানালে এই ওষুধগুলো একসাথে খাবেন না।"
    ),
    "moderate": (
        "DDInter অনুযায়ী এটি একটি মাঝারি ইন্টারঅ্যাকশন। একসাথে খাওয়ার আগে ডাক্তার বা "
        "ফার্মাসিস্টকে জিজ্ঞেস করুন; বাড়তি পর্যবেক্ষণ বা ডোজ বদলের দরকার হতে পারে।"
    ),
    "minor": ("DDInter অনুযায়ী এটি একটি সামান্য ইন্টারঅ্যাকশন। আপনি দুটিই খান, তা ডাক্তার বা ফার্মাসিস্টকে জানান।"),
}


def _name_map(seed_dir: Path) -> dict[str, str]:
    doc = json.loads((seed_dir / "generics.json").read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for record in doc["records"]:
        name = record["name"]
        for alias in [name, *DDINTER_ALIASES.get(name, [])]:
            mapping[alias.strip().casefold()] = name
    return mapping


def extract(folder: Path, seed_dir: Path) -> tuple[list[dict], list[str], int]:
    """Return (interaction records, generics not found in DDInter, number of files read)."""
    names = _name_map(seed_dir)
    files = sorted(folder.glob("ddinter_downloads_code_*.csv"))
    seen_names: set[str] = set()
    pairs: dict[tuple[str, str], str] = {}

    for path in files:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                raw_a = (row.get("Drug_A") or "").strip().casefold()
                raw_b = (row.get("Drug_B") or "").strip().casefold()
                a, b = names.get(raw_a), names.get(raw_b)
                seen_names.update(n for n in (a, b) if n)
                level = (row.get("Level") or "").strip().casefold()
                if not a or not b or a == b or level not in SEVERITY_RANK:
                    continue
                key = (a, b) if a.casefold() < b.casefold() else (b, a)
                if SEVERITY_RANK[level] > SEVERITY_RANK.get(pairs.get(key, ""), 0):
                    pairs[key] = level

    records = [
        {
            "generic_a": a,
            "generic_b": b,
            "severity": level,
            "description": DESCRIPTIONS[level],
            "description_bn": DESCRIPTIONS_BN[level],
        }
        for (a, b), level in sorted(pairs.items(), key=lambda kv: (-SEVERITY_RANK[kv[1]], kv[0]))
    ]
    missing = sorted(set(names.values()) - seen_names)
    return records, missing, len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder with ddinter_downloads_code_*.csv")
    parser.add_argument("--seed-dir", type=Path, default=get_settings().seed_dir)
    args = parser.parse_args()

    records, missing, file_count = extract(args.folder, args.seed_dir)
    if file_count == 0:
        print(f"No ddinter_downloads_code_*.csv files in {args.folder}")
        return 1
    if not records:
        print("No interactions found between our generics; interactions.json NOT written.")
        return 1

    doc = {
        "meta": {
            "dataset": "interactions",
            "source": "DDInter (https://ddinter.scbdd.com), CC BY-NC-SA 4.0",
            "is_sample": False,
            "note": "Severity levels from DDInter. Descriptions are generic per severity level.",
        },
        "records": records,
    }
    out = args.seed_dir / "interactions.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {lvl: sum(r["severity"] == lvl for r in records) for lvl in SEVERITY_RANK}
    print(f"Read {file_count} files. Wrote {len(records)} interactions to {out}: {counts}")
    if missing:
        print("Generics not found in DDInter (check DDINTER_ALIASES):", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
