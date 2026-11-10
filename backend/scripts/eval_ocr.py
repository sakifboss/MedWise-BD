"""Measure how well prescription reading and matching work on real photos.

Reads data/eval/prescriptions/<id>.jpg|png|webp with <id>.json ground truth, runs the app's real
GeminiExtractor on each image (resized exactly like the app does before upload), then the app's
match_prescription against a temporary SQLite database loaded from data/seed.

Gemini's answer for each image is cached in data/eval/cache/<id>.json, so re-running only
re-scores; --refresh calls Gemini again. Both folders are gitignored (personal data).

Usage (from backend/, needs GEMINI_API_KEY in backend/.env):
    python scripts/eval_ocr.py          # read (cached when possible), score, write results.md
    python scripts/eval_ocr.py --refresh --only rx01,rx02
    python scripts/eval_ocr.py --threshold 90 --no-write
"""

import argparse
import hashlib
import io
import json
import re
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.schemas.seed import normalize_strength  # noqa: E402
from app.services.ocr import ExtractedMedicine  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
DEFAULT_THRESHOLD = 85.0

# Same as frontend/src/lib/image.ts: longest side 2000 px, JPEG quality 0.85.
APP_MAX_SIDE = 2000
APP_JPEG_QUALITY = 85


# ---------------------------------------------------------------- ground truth


@dataclass(frozen=True)
class TruthMedicine:
    name: str
    strength: str | None
    generic: str | None = None  # set when the written name differs from the catalog's brand name


def load_truth(path: Path) -> list[TruthMedicine]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        TruthMedicine(m["name"], m.get("strength"), m.get("generic")) for m in data["medicines"]
    ]


def load_unreadable(path: Path) -> int:
    """Lines on the page that nobody could read (left out of the ground truth): up to this many
    medicines the model reads that match nothing are not counted against precision."""
    return int(json.loads(path.read_text(encoding="utf-8")).get("unreadable", 0))


# ---------------------------------------------------------------- comparing names and strengths


# Dosage-form words a reader may add around the name ("Benostar mouthwash", "Viodin M/W").
_FORM_WORDS = re.compile(
    r"(?<![a-z])(tabs?|tablets?|caps?|capsules?|syp|syr|syrup|susp|suspension|mouthwash|m/w|"
    r"drops?|cream|gel|inj|injection|oint|ointment)(?![a-z])\.?"
)


def norm_name(name: str) -> str:
    """Lowercase, without dosage-form words, spaces, dots or hyphens:
    "Ace Plus" == "AcePlus", "Viodin M/W" == "Viodin"."""
    lowered = name.casefold()
    stripped = _FORM_WORDS.sub(" ", lowered)
    if stripped.strip():  # never strip a name down to nothing
        lowered = stripped
    return re.sub(r"[\s.\-]+", "", lowered)


def name_score(a: str, b: str) -> float:
    return fuzz.ratio(norm_name(a), norm_name(b))


_STRENGTH = re.compile(r"^\s*([\d.]+)\s*(.*?)\s*$")


def _split_strength(value: str) -> tuple[str, str]:
    try:
        value = normalize_strength(value)
    except Exception:  # unusual text: compare as written
        value = value.strip().casefold()
    match = _STRENGTH.match(value)
    if not match:
        return value, ""
    number = match.group(1).rstrip("0").rstrip(".") if "." in match.group(1) else match.group(1)
    return number, match.group(2).casefold()


def strengths_agree(a: str | None, b: str | None) -> bool:
    """Only compared when both sides have one. A bare number ("Romycin 500", as doctors often
    write) agrees with the same number in any unit ("500 mg")."""
    if not a or not b:
        return True
    (num_a, unit_a), (num_b, unit_b) = _split_strength(a), _split_strength(b)
    if num_a != num_b:
        return False
    return not unit_a or not unit_b or unit_a == unit_b


def dedupe(medicines: Sequence[ExtractedMedicine]) -> list[ExtractedMedicine]:
    """One entry per normalised name; keep a written strength if any copy has one."""
    kept: dict[str, ExtractedMedicine] = {}
    for m in medicines:
        key = norm_name(m.name)
        if key not in kept or (kept[key].strength is None and m.strength):
            kept[key] = m
    return list(kept.values())


# ---------------------------------------------------------------- reading score


@dataclass(frozen=True)
class Pair:
    truth: int  # index into the ground truth
    extracted: int  # index into the (de-duplicated) extraction
    score: float


def pair_names(
    truth: Sequence[TruthMedicine], extracted: Sequence[ExtractedMedicine], threshold: float
) -> list[Pair]:
    """Best one-to-one pairs whose names score >= threshold (highest score first)."""
    candidates = sorted(
        (
            Pair(t, e, name_score(tm.name, em.name))
            for t, tm in enumerate(truth)
            for e, em in enumerate(extracted)
        ),
        key=lambda p: -p.score,
    )
    used_t: set[int] = set()
    used_e: set[int] = set()
    pairs = []
    for p in candidates:
        if p.score < threshold or p.truth in used_t or p.extracted in used_e:
            continue
        pairs.append(p)
        used_t.add(p.truth)
        used_e.add(p.extracted)
    return sorted(pairs, key=lambda p: p.truth)


@dataclass
class Reading:
    truth_count: int
    extracted_count: int
    correct: list[Pair] = field(default_factory=list)
    wrong_strength: list[Pair] = field(default_factory=list)
    missed: list[int] = field(default_factory=list)  # truth indexes not read
    extra: list[int] = field(default_factory=list)  # extracted indexes with no truth
    unscored: list[int] = field(default_factory=list)  # extras taken to be the unreadable lines

    @property
    def inexact(self) -> list[Pair]:
        """Counted as correct, but the names are not identical: check these by eye."""
        return [p for p in self.correct if p.score < 100]

    @property
    def scored_extracted(self) -> int:
        """Precision's denominator: medicines read, minus the reads of unreadable lines."""
        return self.extracted_count - len(self.unscored)


def score_reading(
    truth: Sequence[TruthMedicine],
    extracted: Sequence[ExtractedMedicine],
    threshold: float,
    unreadable: int = 0,
) -> Reading:
    pairs = pair_names(truth, extracted, threshold)
    reading = Reading(len(truth), len(extracted))
    for p in pairs:
        ok = strengths_agree(truth[p.truth].strength, extracted[p.extracted].strength)
        (reading.correct if ok else reading.wrong_strength).append(p)
    paired_t = {p.truth for p in pairs}
    paired_e = {p.extracted for p in pairs}
    reading.missed = [i for i in range(len(truth)) if i not in paired_t]
    extras = [i for i in range(len(extracted)) if i not in paired_e]
    # The extras least like any true name are the likeliest reads of the unreadable lines.
    likeness = {
        i: max((name_score(t.name, extracted[i].name) for t in truth), default=0.0) for i in extras
    }
    unscored = set(sorted(extras, key=lambda i: likeness[i])[:unreadable])
    reading.unscored = sorted(unscored)
    reading.extra = [i for i in extras if i not in unscored]
    return reading


# ---------------------------------------------------------------- matching score


@dataclass(frozen=True)
class Expected:
    generic: str
    strength: str | None  # None: any strength of that generic is right


@dataclass(frozen=True)
class Suggestion:
    generic: str
    strength: str


@dataclass
class Matching:
    in_catalog: int = 0
    matched: int = 0  # the app pre-selected the right generic + strength
    offered: int = 0  # the right one was among the options the user can pick from
    failures: list[str] = field(default_factory=list)


def _is_expected(expected: Expected, got: Suggestion) -> bool:
    return got.generic == expected.generic and strengths_agree(expected.strength, got.strength)


def catalog_lookup(
    brands: dict[str, set[str]], generics: dict[str, str]
) -> Callable[[TruthMedicine], Expected | None]:
    """brands: normalised brand name -> generic names; generics: normalised name -> name."""

    def lookup(m: TruthMedicine) -> Expected | None:
        if m.generic:
            generic = generics.get(norm_name(m.generic))
        elif norm_name(m.name) in brands:
            options = brands[norm_name(m.name)]
            generic = next(iter(options)) if len(options) == 1 else None
        else:
            generic = generics.get(norm_name(m.name))
        return Expected(generic, m.strength) if generic else None

    return lookup


def score_matching(
    truth: Sequence[TruthMedicine],
    reading: Reading,
    suggestions: Sequence[Suggestion | None],
    lookup: Callable[[TruthMedicine], Expected | None],
    offered: Sequence[Sequence[Suggestion]] | None = None,
) -> Matching:
    """Of the true medicines in our catalog, how many got the right suggestion (generic + strength).

    suggestions[i] is what the app pre-selected for extracted medicine i (None: nothing);
    offered[i] is every option it listed for the user to choose from."""
    matching = Matching()
    by_truth = {p.truth: p.extracted for p in [*reading.correct, *reading.wrong_strength]}
    for i, m in enumerate(truth):
        expected = lookup(m)
        if expected is None:
            continue
        matching.in_catalog += 1
        if i not in by_truth:
            matching.failures.append(f"{m.name}: not read")
            continue
        got = suggestions[by_truth[i]]
        options = offered[by_truth[i]] if offered is not None else ([got] if got else [])
        in_options = any(_is_expected(expected, o) for o in options)
        matching.offered += in_options
        if got is not None and _is_expected(expected, got):
            matching.matched += 1
        elif got is None:
            note = " (right option listed)" if in_options else ""
            matching.failures.append(f"{m.name}: no suggestion{note}")
        else:
            matching.failures.append(f"{m.name}: suggested {got.generic} {got.strength}")
    return matching


# ---------------------------------------------------------------- totals


@dataclass
class ImageResult:
    image_id: str
    subset: str
    truth: list[TruthMedicine]
    extracted: list[ExtractedMedicine]
    reading: Reading
    matching: Matching
    model: str | None
    error: str | None = None


@dataclass
class Totals:
    images: int = 0
    truth: int = 0
    extracted: int = 0
    correct: int = 0
    in_catalog: int = 0
    matched: int = 0
    offered: int = 0
    errors: int = 0

    def add(self, r: ImageResult) -> None:
        self.images += 1
        self.truth += r.reading.truth_count
        self.extracted += r.reading.scored_extracted
        self.correct += len(r.reading.correct)
        self.in_catalog += r.matching.in_catalog
        self.matched += r.matching.matched
        self.offered += r.matching.offered
        self.errors += r.error is not None

    @property
    def recall(self) -> float | None:
        return self.correct / self.truth if self.truth else None

    @property
    def precision(self) -> float | None:
        return self.correct / self.extracted if self.extracted else None

    @property
    def match_rate(self) -> float | None:
        return self.matched / self.in_catalog if self.in_catalog else None

    @property
    def offered_rate(self) -> float | None:
        return self.offered / self.in_catalog if self.in_catalog else None


def totals_by_subset(results: Iterable[ImageResult]) -> dict[str, Totals]:
    out: dict[str, Totals] = {}
    for r in results:
        out.setdefault(r.subset, Totals()).add(r)
        out.setdefault("overall", Totals()).add(r)
    return out


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


# ---------------------------------------------------------------- images and cache


def prepare_image(raw: bytes) -> bytes:
    """Resize and re-encode exactly like the app before upload (frontend/src/lib/image.ts)."""
    from PIL import Image, ImageOps  # dev dependency, only needed here

    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        scale = min(1.0, APP_MAX_SIDE / max(image.size))
        if scale < 1.0:
            size = (round(image.width * scale), round(image.height * scale))
            image = image.resize(size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        image.save(out, "JPEG", quality=APP_JPEG_QUALITY)
        return out.getvalue()


def read_cache(path: Path, image_hash: str) -> tuple[list[ExtractedMedicine], str | None] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("image_sha256") != image_hash:
        return None  # the photo changed: read it again
    meds = [ExtractedMedicine(m["name"], m.get("strength")) for m in data["medicines"]]
    return meds, data.get("model")


def write_cache(
    path: Path, image_hash: str, medicines: Sequence[ExtractedMedicine], model: str | None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "image_sha256": image_hash,
        "model": model,
        "read_on": date.today().isoformat(),
        "medicines": [{"name": m.name, "strength": m.strength} for m in medicines],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_images(folder: Path, only: set[str] | None) -> list[Path]:
    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    return [p for p in images if only is None or p.stem in only]


def subset_of(image_id: str, subsets: dict[str, list[str]]) -> str:
    return next((name for name, ids in subsets.items() if image_id in ids), "other")


# ---------------------------------------------------------------- report


def describe(r: ImageResult) -> list[str]:
    lines = []
    if r.error:
        lines.append(f"    ERROR: {r.error}")
    for i in r.reading.missed:
        lines.append(f"    missed:         {r.truth[i].name} {r.truth[i].strength or ''}".rstrip())
    for p in r.reading.wrong_strength:
        t, e = r.truth[p.truth], r.extracted[p.extracted]
        lines.append(f"    wrong strength: {t.name} {t.strength} (read {e.name} {e.strength})")
    for p in r.reading.inexact:
        t, e = r.truth[p.truth], r.extracted[p.extracted]
        lines.append(f"    close name:     {t.name} read as {e.name} ({p.score:.0f})")
    for i in r.reading.extra:
        m = r.extracted[i]
        lines.append(f"    extra:          {m.name} {m.strength or ''}".rstrip())
    for i in r.reading.unscored:
        m = r.extracted[i]
        lines.append(f"    unreadable line: read as {m.name} (not scored)")
    for f in r.matching.failures:
        lines.append(f"    match miss:     {f}")
    return lines


TOTALS_HEADER = (
    "| Subset | Images | On prescriptions | Read | Correct | Recall | Precision "
    "| Matched | Match rate | Offered | Offered rate |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|"
)

SUBSET_NOTES = {
    "real_handwritten": "real handwritten prescriptions (scanned with CamScanner)",
    "synthetic_printed": "computer-generated printed prescriptions with fictional medicine names "
    "(shows the pipeline works; not real-world accuracy; no catalog matches possible)",
    "degraded_copies": "blurred / dimmed and rotated / low-resolution copies of real images",
}


def results_markdown(
    results: Sequence[ImageResult],
    threshold: float,
    excluded: dict | None,
    first_choice: str | None = None,
) -> str:
    totals = totals_by_subset(results)
    models = Counter(r.model for r in results if r.model)
    order = [s for s in (*SUBSET_NOTES, "other") if s in totals] + ["overall"]
    fallback_note = (
        f"The app's first-choice model ({first_choice}) did not answer (busy), so its fallback"
        " models did, as they would for a user at that moment."
        if first_choice and models and first_choice not in models
        else ""
    )
    rows = [
        f"| {name} | {t.images} | {t.truth} | {t.extracted} | {t.correct} | {pct(t.recall)} | "
        f"{pct(t.precision)} | {t.matched}/{t.in_catalog} | {pct(t.match_rate)} | "
        f"{t.offered}/{t.in_catalog} | {pct(t.offered_rate)} |"
        for name in order
        for t in [totals[name]]
    ]
    per_image = []
    for r in results:
        missed = ", ".join(r.truth[i].name for i in r.reading.missed) or "-"
        extra = ", ".join(r.extracted[i].name for i in r.reading.extra) or "-"
        per_image.append(
            f"| {r.image_id} | {r.subset} | {len(r.reading.correct)}/{r.reading.truth_count} | "
            f"{missed} | {extra} | {r.matching.matched}/{r.matching.in_catalog} |"
        )
    notes = "\n".join(
        f"- **{name}**: {SUBSET_NOTES[name]}." for name in SUBSET_NOTES if name in totals
    )
    excluded_line = (
        f"\n- Not scored: {excluded['reason']}" if excluded and excluded.get("reason") else ""
    )
    return f"""# OCR evaluation results

Run on {date.today().isoformat()} with `backend/scripts/eval_ocr.py`. {len(results)} images.
Models that answered: {", ".join(f"{m} ({n})" for m, n in models.most_common()) or "none"}.
{fallback_note}
Images are resized like the app (longest side {APP_MAX_SIDE} px, JPEG quality {APP_JPEG_QUALITY}).

## How it is scored

- **Reading**: a medicine read from the image is correct when its name matches the ground truth
  (rapidfuzz ratio >= {threshold:g}, ignoring case, spaces, dots, hyphens and dosage-form words
  such as "tab" or "mouthwash") and, when both have a strength, the strengths agree (a bare
  number like "500" agrees with "500 mg").
  Recall = correct / medicines on the prescriptions; precision = correct / medicines read.
  Duplicates read from one image are counted once. A read of a line nobody could read (see
  "Not scored" below) does not count against precision.
- **Matching**: of the medicines on the prescriptions that exist in our catalog, how many the app
  pre-selected with the right generic and strength ("Matched"), and how many it at least listed
  among the options the user picks from ("Offered").

## Totals

{TOTALS_HEADER}
{chr(10).join(rows)}

## The images

{notes}{excluded_line}
- Ground truth was written by the team from the images; names they could not read are left out.
- This file holds only file ids and medicine names, no patient or doctor details.

## Per image

| Image | Subset | Correct | Missed | Extra (read, not on the prescription) | Matched |
|---|---|---|---|---|---|
{chr(10).join(per_image)}
"""


# ---------------------------------------------------------------- run


def catalog_from_db(session: Session) -> tuple[dict[str, set[str]], dict[str, str]]:
    from app.models import Brand, Generic

    brands: dict[str, set[str]] = {}
    for brand_name, generic_name in session.execute(
        select(Brand.name, Generic.name).join(Generic, Brand.generic_id == Generic.id)
    ):
        brands.setdefault(norm_name(brand_name), set()).add(generic_name)
    generics = {norm_name(name): name for (name,) in session.execute(select(Generic.name))}
    return brands, generics


def app_matches(
    session: Session, extracted: Sequence[ExtractedMedicine]
) -> tuple[list[Suggestion | None], list[list[Suggestion]]]:
    """What the app pre-selects for each extracted medicine, and every option it lists."""
    from app.services.prescription import match_prescription

    suggested: list[Suggestion | None] = []
    offered: list[list[Suggestion]] = []
    for match in match_prescription(session, list(extracted)):
        options = [Suggestion(o.generic_name, o.strength) for o in match.options]
        offered.append(options)
        suggested.append(None if match.suggested_index is None else options[match.suggested_index])
    return suggested, offered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate prescription reading and matching.")
    parser.add_argument("--eval-dir", type=Path, default=EVAL_DIR)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--refresh", action="store_true", help="call Gemini even when cached")
    parser.add_argument("--delay", type=float, default=6.0, help="seconds between Gemini calls")
    parser.add_argument("--only", help="comma-separated image ids, e.g. rx01,rx02")
    parser.add_argument("--no-write", action="store_true", help="do not write results.md")
    args = parser.parse_args(argv)

    from app.core.config import get_settings
    from app.core.db import make_engine
    from app.core.errors import AppError
    from app.services.ocr import GeminiExtractor
    from scripts.import_data import run_import

    folder = args.eval_dir / "prescriptions"
    cache_dir = args.eval_dir / "cache"
    subsets_file = args.eval_dir / "subsets.json"
    subsets_data = (
        json.loads(subsets_file.read_text(encoding="utf-8")) if subsets_file.exists() else {}
    )
    subsets: dict[str, list[str]] = subsets_data.get("subsets", {})
    only = set(args.only.split(",")) if args.only else None
    images = find_images(folder, only)
    if not images:
        print(f"No images in {folder}")
        return 1
    missing = [p.name for p in images if not p.with_suffix(".json").exists()]
    if missing:
        print(f"Ground truth missing for: {', '.join(missing)}")
        return 1

    settings = get_settings()
    extractor: GeminiExtractor | None = None
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(f"sqlite:///{(Path(tmp) / 'eval.db').as_posix()}")
        imported = run_import(settings.seed_dir, engine)
        if not imported.ok:
            print("Seed import failed:", *imported.errors, sep="\n  ")
            return 1
        results: list[ImageResult] = []
        last_call = 0.0
        with Session(engine) as session:
            brands, generics = catalog_from_db(session)
            lookup = catalog_lookup(brands, generics)
            for path in images:
                image_id = path.stem
                truth = load_truth(path.with_suffix(".json"))
                sent = prepare_image(path.read_bytes())
                image_hash = hashlib.sha256(sent).hexdigest()
                cache_path = cache_dir / f"{image_id}.json"
                cached = None if args.refresh else read_cache(cache_path, image_hash)
                error = None
                if cached:
                    medicines, model = cached
                    source = "cache"
                else:
                    if extractor is None:
                        extractor = GeminiExtractor(settings)
                    wait = args.delay - (time.monotonic() - last_call)
                    if last_call and wait > 0:
                        time.sleep(wait)
                    last_call = time.monotonic()
                    try:
                        medicines, model = extractor(sent, "image/jpeg"), extractor.last_model
                        write_cache(cache_path, image_hash, medicines, model)
                    except AppError as exc:
                        medicines, model, error = [], None, f"{exc.code}: {exc.message}"
                    source = "gemini"
                extracted = dedupe(medicines)
                unreadable = load_unreadable(path.with_suffix(".json"))
                reading = score_reading(truth, extracted, args.threshold, unreadable)
                suggested, offered = app_matches(session, extracted)
                matching = score_matching(truth, reading, suggested, lookup, offered)
                result = ImageResult(
                    image_id,
                    subset_of(image_id, subsets),
                    truth,
                    extracted,
                    reading,
                    matching,
                    model,
                    error,
                )
                results.append(result)
                print(
                    f"{image_id} [{result.subset}, {source}] read {len(reading.correct)}"
                    f"/{reading.truth_count}, matched {matching.matched}/{matching.in_catalog}"
                    f" (offered {matching.offered})"
                )
                for line in describe(result):
                    print(line)
        engine.dispose()

    print()
    for name, t in totals_by_subset(results).items():
        print(
            f"{name:18} images {t.images:2}  recall {pct(t.recall):>6} ({t.correct}/{t.truth})"
            f"  precision {pct(t.precision):>6} ({t.correct}/{t.extracted})"
            f"  matching {pct(t.match_rate):>6} ({t.matched}/{t.in_catalog})"
            f"  offered {pct(t.offered_rate):>6} ({t.offered}/{t.in_catalog})"
            + (f"  errors {t.errors}" if t.errors else "")
        )
    if not args.no_write:
        out = args.eval_dir / "results.md"
        out.write_text(
            results_markdown(
                results,
                args.threshold,
                subsets_data.get("excluded"),
                settings.gemini_models[0],
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
