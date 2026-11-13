"""Stable brand codes ("BR" + 5 digits, e.g. BR00042) for data/seed/brands.json.

Database ids change whenever the seed import rebuilds the tables, so anything that must outlive a
deploy (share links, saved lists, page links, templates, QR codes) refers to a brand by its code.

Rules: a brand keeps its code while its name + manufacturer + strength + dosage form stay the same
(a price change keeps it); a new brand gets the next unused number; a removed brand's code is
retired (meta.retired_codes) and never given out again.
"""

import re

CODE = re.compile(r"^BR\d{5}$")

BrandKey = tuple[str, str, str, str]


def brand_key(record: dict) -> BrandKey:
    return (
        record["name"].strip().casefold(),
        record["manufacturer"].strip().casefold(),
        record["strength"].strip().casefold(),
        record["dosage_form"].strip().casefold(),
    )


def _number(code: str) -> int:
    return int(code[2:])


def format_code(number: int) -> str:
    return f"BR{number:05d}"


def assign_codes(records: list[dict], previous: dict | None) -> tuple[list[dict], list[str]]:
    """Give every record a code, keeping codes from the previous brands.json document.

    Returns (records with "code" first, sorted retired codes). Records are not reordered.
    """
    old_records = (previous or {}).get("records", [])
    retired = set((previous or {}).get("meta", {}).get("retired_codes", []))
    known = {brand_key(r): r["code"] for r in old_records if CODE.match(r.get("code", ""))}
    used = set(known.values()) | retired
    next_number = max((_number(c) for c in used), default=0) + 1

    out: list[dict] = []
    kept: set[str] = set()
    for record in records:
        code = known.get(brand_key(record))
        if code is None or code in kept:
            code = format_code(next_number)
            next_number += 1
        kept.add(code)
        out.append({"code": code, **{k: v for k, v in record.items() if k != "code"}})

    retired |= set(known.values()) - kept
    return out, sorted(retired)
