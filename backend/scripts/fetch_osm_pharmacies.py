"""Fetch Sylhet city pharmacies and area names from OpenStreetMap (Overpass API).

Writes data/seed/pharmacies.json (pharmacies) and data/seed/sylhet_areas.json (areas people can
pick when they do not share their location). OpenStreetMap data is (c) OpenStreetMap contributors,
licensed under the ODbL; credit it wherever the list is shown.

Usage (from backend/):
    python scripts/fetch_osm_pharmacies.py                       # fetch and write both files
    python scripts/fetch_osm_pharmacies.py --from-file saved.json   # rebuild from a saved answer
    python scripts/import_data.py --dry-run

Rules (printed in the report, and kept in each file's meta):
- Only amenity=pharmacy (healthcare=pharmacy and shop=chemist are counted, not included).
- Excluded: entries without a name, and homeopathic, herbal, Ayurvedic or Unani shops (by name:
  Homeo, হোমিও, Herbal, Ayurvedic, Unani; or by tags such as healthcare:speciality=homeopathy).
- Fields the team keeps by hand (is_partner, partner_since, hide_phone) survive a re-fetch,
  matched by OSM id. Adding a partner is a data-only change in pharmacies.json.
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.schemas.seed import SYLHET_BBOX  # noqa: E402

OVERPASS_SERVERS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

PLACE_TYPES = ("suburb", "neighbourhood", "quarter", "locality", "square", "borough", "village")
# Areas OSM has only as a junction, road or landmark: OSM element -> (English, Bangla) name.
AREA_ANCHORS: dict[str, tuple[str, str]] = {
    "node/264490171": ("Ambarkhana", "আম্বরখানা"),  # আম্বরখানা মোড় (junction)
    "node/264611266": ("Chowhatta", "চৌহাট্টা"),  # Chowhatta Moor
    "node/4121728523": ("Pathantula", "পাঠানটুলা"),  # Pathantula Point
    "node/264491236": ("Upashahar", "উপশহর"),  # Rose View Uposhohor Point
    "way/528899502": ("Akhalia", "আখালিয়া"),  # Akhalia (road)
    "way/530948418": ("Lamabazar", "লামাবাজার"),  # Lamabazar Jame Masjid
    "way/354424186": ("Kumarpara", "কুমারপাড়া"),  # Kumarpara Road
    "way/1107198636": ("Subidbazar", "সুবিদবাজার"),  # Subid Bazar Road
    "way/1509312201": ("Kumargaon", "কুমারগাঁও"),  # Shajahanullah United Kumargaon power plant
    "node/765894619": ("Dargah (Hazrat Shahjalal Mazar)", "দরগাহ (হযরত শাহজালাল মাজার)"),
    "way/539407023": (
        "SUST (Shahjalal University)",
        "শাবিপ্রবি (শাহজালাল বিশ্ববিদ্যালয়)",
    ),  # Central Auditorium
}
# Better display names for some OSM places, by OSM element.
PLACE_NAMES: dict[str, tuple[str, str]] = {
    "node/5146598263": ("Zindabazar", "জিন্দাবাজার"),  # Zindabazar Point
    "node/6296963510": ("Modina Market", "মদিনা মার্কেট"),
    "node/4762165002": ("South Surma", "দক্ষিণ সুরমা"),
    "node/6296963513": ("Temukhi", "টেমুখী"),
}
# OSM places left out because another entry already names the same area.
SKIP_PLACES = {"node/5103775457"}  # Tilaghar Point: the suburb Tilagar covers it
# Not in OpenStreetMap as a place or landmark: to be added by the team with a phone's GPS.
# Found on OSM on 2026-11-13 (Kumargaon, Subidbazar); add names here that OSM does not have.
TO_ADD_BY_GPS: tuple[str, ...] = ()

EXCLUDED_NAME = re.compile(r"homeo|হোমিও|herbal|ayurved|unani", re.I)
EXCLUDED_TAGS = {
    "healthcare:speciality": re.compile(r"homeopath|herbal|ayurved|unani", re.I),
    "healthcare": re.compile(r"^alternative$", re.I),
    "shop": re.compile(r"^herbalist$", re.I),
    "homeopathy": re.compile(r"^yes$", re.I),
}
AREAS_NOTE = (
    "Areas to pick when location is not shared: OSM places, plus OSM junctions, roads and "
    "landmarks for areas OSM has no place for. Bangla names drafted by MedWise BD."
)
HAND_FIELDS = ("is_partner", "partner_since", "hide_phone")


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
    nodes = ",".join(k.split("/")[1] for k in AREA_ANCHORS if k.startswith("node/"))
    ways = ",".join(k.split("/")[1] for k in AREA_ANCHORS if k.startswith("way/"))
    return f"""[out:json][timeout:120];
(
  nwr["amenity"="pharmacy"]{box};
  nwr["healthcare"="pharmacy"]{box};
  nwr["shop"="chemist"]{box};
  node["place"~"^({"|".join(PLACE_TYPES)})$"]{box};
  node(id:{nodes});
  way(id:{ways});
);
out center tags;"""


def fetch(bbox: tuple[float, float, float, float]) -> list[dict]:
    body = urllib.parse.urlencode({"data": overpass_query(bbox)}).encode()
    last: Exception | None = None
    for server in OVERPASS_SERVERS:
        try:
            request = urllib.request.Request(
                server, data=body, headers={"User-Agent": "MedWiseBD-data/1.0"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)["elements"]
        except Exception as exc:  # busy servers answer 502/504 or time out: try the next one
            last = exc
            time.sleep(5)
    raise RuntimeError(f"Overpass did not answer: {last}")


def ref(element: dict) -> str:
    return f"{element['type']}/{element['id']}"


def position(element: dict) -> tuple[float, float] | None:
    if "lat" in element:
        return element["lat"], element["lon"]
    center = element.get("center")
    return (center["lat"], center["lon"]) if center else None


def inside(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    s, w, n, e = bbox
    return s <= lat <= n and w <= lon <= e


def address(tags: dict) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"].strip()
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    parts = [street, tags.get("addr:suburb"), tags.get("addr:city")]
    joined = ", ".join(p.strip() for p in parts if p and p.strip())
    return joined or None


def phone(tags: dict) -> str | None:
    for key in ("phone", "contact:phone", "contact:mobile", "mobile"):
        if tags.get(key):
            return tags[key].split(";")[0].strip()
    return None


def exclusion_reason(tags: dict) -> str | None:
    """Why a pharmacy is left out, or None to keep it."""
    name = " ".join(filter(None, (tags.get("name"), tags.get("name:en"), tags.get("name:bn"))))
    if not name.strip():
        return "no name"
    if match := EXCLUDED_NAME.search(name):
        return f"name says homeopathic/herbal/Ayurvedic/Unani ({match.group(0)})"
    for key, pattern in EXCLUDED_TAGS.items():
        if tags.get(key) and pattern.search(tags[key]):
            return f"tagged {key}={tags[key]}"
    return None


def pharmacy_record(element: dict) -> dict | None:
    tags = element.get("tags", {})
    pos = position(element)
    if not pos:
        return None
    return {
        "name": " ".join((tags.get("name:en") or tags.get("name") or "").split()),
        "name_bn": " ".join((tags.get("name:bn") or "").split()) or None,
        "lat": round(pos[0], 7),
        "lon": round(pos[1], 7),
        "address": address(tags),
        "phone": phone(tags),
        "source": "osm",
        "osm_type": element["type"],
        "osm_id": element["id"],
        "is_partner": False,
        "partner_since": None,
        "hide_phone": False,
    }


def keep_hand_fields(records: list[dict], previous: list[dict]) -> list[dict]:
    """Carry is_partner, partner_since and hide_phone over from the last file, by OSM id."""
    old = {(r.get("osm_type"), r.get("osm_id")): r for r in previous}
    for r in records:
        before = old.get((r["osm_type"], r["osm_id"]))
        if before:
            for field in HAND_FIELDS:
                if field in before:
                    r[field] = before[field]
    return records


def build_pharmacies(
    elements: list[dict], previous: list[dict]
) -> tuple[list[dict], list[dict], Counter]:
    counts: Counter = Counter()
    kept: list[dict] = []
    excluded: list[dict] = []
    seen: set[str] = set()
    for element in elements:
        tags = element.get("tags", {})
        if ref(element) in seen:
            continue
        if tags.get("amenity") == "pharmacy":
            counts["amenity=pharmacy"] += 1
        elif tags.get("healthcare") == "pharmacy":
            counts["healthcare=pharmacy only (not included)"] += 1
            continue
        elif tags.get("shop") == "chemist":
            counts["shop=chemist (not included)"] += 1
            continue
        else:
            continue
        seen.add(ref(element))
        record = pharmacy_record(element)
        if record is None:
            continue
        reason = exclusion_reason(tags)
        if reason:
            excluded.append({"osm": ref(element), "name": tags.get("name"), "reason": reason})
            continue
        kept.append(record)
    kept.sort(key=lambda r: (r["name"].casefold(), r["osm_id"]))
    return keep_hand_fields(kept, previous), excluded, counts


def build_areas(elements: list[dict], bbox: tuple[float, float, float, float]) -> list[dict]:
    areas: dict[str, dict] = {}
    for element in elements:
        tags = element.get("tags", {})
        key = ref(element)
        pos = position(element)
        if not pos:
            continue
        if key in SKIP_PLACES:
            continue
        if key in AREA_ANCHORS:
            name, name_bn = AREA_ANCHORS[key]
            kind = "landmark"
        elif element["type"] == "node" and tags.get("place") in PLACE_TYPES and tags.get("name"):
            name, name_bn = PLACE_NAMES.get(
                key, (tags.get("name:en") or tags["name"], tags.get("name:bn") or "")
            )
            kind = tags["place"]
        else:
            continue
        if not inside(*pos, bbox) or name.casefold() in areas:
            continue
        areas[name.casefold()] = {
            "name": name.strip(),
            "name_bn": (name_bn or "").strip() or None,
            "lat": round(pos[0], 7),
            "lon": round(pos[1], 7),
            "kind": kind,
            "osm": key,
        }
    return sorted(areas.values(), key=lambda a: a["name"].casefold())


def meta(dataset: str, bbox: tuple[float, float, float, float], **extra: object) -> dict:
    return {
        "dataset": dataset,
        "source": "OpenStreetMap contributors (https://www.openstreetmap.org/copyright)",
        "licence": "ODbL 1.0",
        "is_sample": False,
        "fetched": date.today().isoformat(),
        "bbox_south_west_north_east": list(bbox),
        **extra,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed-dir", type=Path, default=get_settings().seed_dir)
    parser.add_argument("--from-file", type=Path, help="Overpass JSON saved earlier (no network)")
    parser.add_argument("--save-raw", type=Path, help="also save the Overpass answer here")
    args = parser.parse_args(argv)

    if args.from_file:
        elements = json.loads(args.from_file.read_text(encoding="utf-8"))["elements"]
    else:
        elements = fetch(SYLHET_BBOX)
        if args.save_raw:
            args.save_raw.write_text(
                json.dumps({"elements": elements}, ensure_ascii=False), encoding="utf-8"
            )

    out = args.seed_dir / "pharmacies.json"
    previous = json.loads(out.read_text(encoding="utf-8"))["records"] if out.exists() else []
    pharmacies, excluded, counts = build_pharmacies(elements, previous)
    areas = build_areas(elements, SYLHET_BBOX)

    note = (
        "Fetched with backend/scripts/fetch_osm_pharmacies.py. is_partner, partner_since and "
        "hide_phone are kept by hand and survive a re-fetch. Phone numbers are as published on "
        "OpenStreetMap and may be out of date."
    )
    out.write_text(
        json.dumps(
            {
                "meta": meta("pharmacies", SYLHET_BBOX, note=note, excluded=excluded),
                "records": pharmacies,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    areas_out = args.seed_dir / "sylhet_areas.json"
    areas_out.write_text(
        json.dumps(
            {
                "meta": meta(
                    "sylhet_areas",
                    SYLHET_BBOX,
                    note=AREAS_NOTE,
                    to_add_by_team_gps=list(TO_ADD_BY_GPS),
                ),
                "records": areas,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    named = len(pharmacies)
    with_phone = sum(1 for p in pharmacies if p["phone"])
    print(f"OSM in the box: {dict(counts)}")
    print(f"Wrote {named} pharmacies ({with_phone} with a phone) to {out}")
    print(f"Excluded {len(excluded)}:")
    for e in excluded:
        print(f"  {e['osm']:<18} {str(e['name'])[:40]:40} {e['reason']}")
    print(f"Wrote {len(areas)} areas to {areas_out}: {', '.join(a['name'] for a in areas)}")
    print(f"To add by team GPS later: {', '.join(TO_ADD_BY_GPS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
