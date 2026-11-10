"""Evaluate the symptom guide (P10) on invented cases in data/eval/symptoms.json.

Runs the real pipeline (Gemini, then every server-side check and rule) and reports:
- red-flag recall: of the cases that must show the emergency screen, how many did (must be 100%);
- false alarms: ordinary cases that showed the emergency screen;
- specialty accuracy: of the ordinary cases, how many got an acceptable specialty;
- how often the AI note was dropped, and why.

Each case's raw model answer is cached in data/eval/cache/symptoms/ (gitignored) together with a
hash of the request, so a re-run does not call Gemini again unless the prompt or the case
changed; --refresh forces new calls. From backend/ (needs GEMINI_API_KEY in backend/.env):

    python scripts/eval_symptoms.py              # writes data/eval/symptoms_results.md
    python scripts/eval_symptoms.py --only rf01,sp03 --no-write
"""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import REPO_DIR  # noqa: E402

EVAL_DIR = REPO_DIR / "data" / "eval"


@dataclass(frozen=True)
class Case:
    id: str
    lang: str  # en / bn / banglish (how it is written; the note is asked in Bangla for bn)
    answers: dict
    red_flag: bool
    specialty: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    case: Case
    emergency: bool
    specialty: str | None
    reason: str
    model: str | None
    error: str | None = None

    @property
    def correct(self) -> bool:
        if self.case.red_flag:
            return self.emergency
        return not self.emergency and self.specialty in self.case.specialty


def load_cases(path: Path) -> list[Case]:
    cases = []
    for raw in json.loads(path.read_text(encoding="utf-8"))["cases"]:
        answers = {k: raw[k] for k in ("text", "since", "severity", "age_group", "pregnant")}
        answers["lang"] = "bn" if raw["lang"] == "bn" else "en"
        cases.append(
            Case(
                raw["id"],
                raw["lang"],
                answers,
                bool(raw["red_flag"]),
                tuple(raw.get("specialty", ())),
            )
        )
    return cases


@dataclass
class Totals:
    red_cases: int = 0
    red_caught: int = 0
    ordinary: int = 0
    false_alarms: int = 0
    specialty_right: int = 0
    unanswered: int = 0

    @property
    def red_recall(self) -> float | None:
        return self.red_caught / self.red_cases if self.red_cases else None

    @property
    def specialty_accuracy(self) -> float | None:
        return self.specialty_right / self.ordinary if self.ordinary else None


def totals(outcomes: Iterable[Outcome]) -> Totals:
    t = Totals()
    for o in outcomes:
        if o.error:
            t.unanswered += 1
        if o.case.red_flag:
            t.red_cases += 1
            t.red_caught += o.emergency
        else:
            t.ordinary += 1
            t.false_alarms += o.emergency
            t.specialty_right += o.correct
    return t


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def describe(o: Outcome) -> str:
    want = "emergency" if o.case.red_flag else "/".join(o.case.specialty)
    got = "emergency" if o.emergency else (o.specialty or "-")
    extra = f" ({o.reason})" if o.reason != "ok" else ""
    error = f" ERROR {o.error}" if o.error else ""
    return f"{o.case.id} [{o.case.lang}] want {want}, got {got}{extra}{error}"


def results_markdown(outcomes: list[Outcome], models: Counter, when: date) -> str:
    overall = totals(outcomes)
    by_lang = {
        lang: totals(o for o in outcomes if o.case.lang == lang)
        for lang in ("en", "bn", "banglish")
    }
    reasons = Counter(o.reason for o in outcomes if not o.emergency)
    lines = [
        "# Symptom guide evaluation",
        "",
        f"Date: {when.isoformat()} · Cases: {len(outcomes)} (invented, no real patients; "
        "`data/eval/symptoms.json`) · Models: "
        + (", ".join(f"{m} ({n})" for m, n in models.most_common()) or "none"),
        "",
        "The whole pipeline ran: Gemini, then the strict schema, the medicine/dose/diagnosis",
        "checks and the fixed rules (child -> paediatrics, pregnant -> obstetrics).",
        "",
        "| | Red-flag recall | False alarms | Specialty accuracy |",
        "|---|---|---|---|",
    ]
    for name, t in [("**All**", overall), *((k, v) for k, v in by_lang.items())]:
        lines.append(
            f"| {name} | {t.red_caught}/{t.red_cases} ({pct(t.red_recall)}) | "
            f"{t.false_alarms}/{t.ordinary} | {t.specialty_right}/{t.ordinary} "
            f"({pct(t.specialty_accuracy)}) |"
        )
    lines += [
        "",
        "Red-flag recall must be 100%: every emergency case showed the emergency screen."
        if overall.red_recall == 1.0
        else "**Red-flag recall is below 100%: the PR is not ready.**",
        "",
        "Doctor notes on the ordinary cases: "
        + ", ".join(f"{reason} {n}" for reason, n in reasons.most_common())
        + " (`ok` = the AI note was used; anything else = the note was built from the answers).",
        "",
        "## Misses",
        "",
    ]
    misses = [describe(o) for o in outcomes if not o.correct or o.error]
    lines += [f"- {m}" for m in misses] or ["None."]
    if overall.unanswered:
        lines += ["", f"{overall.unanswered} case(s) got no model answer; run again."]
    return "\n".join(lines) + "\n"


def _cache_key(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the symptom guide.")
    parser.add_argument("--eval-dir", type=Path, default=EVAL_DIR)
    parser.add_argument("--refresh", action="store_true", help="call Gemini even when cached")
    parser.add_argument("--delay", type=float, default=5.0, help="seconds between Gemini calls")
    parser.add_argument("--only", help="comma-separated case ids, e.g. rf01,sp03")
    parser.add_argument("--no-write", action="store_true", help="do not write symptoms_results.md")
    args = parser.parse_args(argv)

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.core.db import make_engine
    from app.models import Brand, Generic, Specialty
    from app.schemas.symptom_guide import SymptomGuideIn
    from app.services.gemini import GeminiClient, GeminiUnavailable
    from app.services.symptom_guide import load_words, request_body, run_guide
    from scripts.import_data import run_import

    settings = get_settings()
    cases = load_cases(args.eval_dir / "symptoms.json")
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
    cache_dir = args.eval_dir / "cache" / "symptoms"
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = GeminiClient(settings) if settings.gemini_api_key else None
    words = load_words(settings.symptom_words_path)

    outcomes: list[Outcome] = []
    models: Counter = Counter()
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(f"sqlite:///{(Path(tmp) / 'eval.db').as_posix()}")
        imported = run_import(settings.seed_dir, engine)
        if not imported.ok:
            print("Seed import failed:", *imported.errors, sep="\n  ")
            return 1
        with Session(engine) as session:
            specialties = {s.key: s.covers for s in session.scalars(select(Specialty))}
            names = sorted(
                {*session.scalars(select(Brand.name)), *session.scalars(select(Generic.name))}
            )
        engine.dispose()  # Windows cannot delete an open database file
        last_call = 0.0
        for case in cases:
            answers = SymptomGuideIn(**case.answers)
            body = request_body(answers, specialties)
            key = _cache_key(body)
            path = cache_dir / f"{case.id}.json"
            cached = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            error = None
            if cached and cached.get("key") == key and not args.refresh:
                text, model = cached["text"], cached["model"]
            elif client is None:
                print("GEMINI_API_KEY is not set and there is no cached answer.")
                return 1
            else:
                wait = args.delay - (time.monotonic() - last_call)
                if last_call and wait > 0:
                    time.sleep(wait)
                last_call = time.monotonic()
                try:
                    text, model = client.generate(body), client.last_model
                    path.write_text(
                        json.dumps({"key": key, "model": model, "text": text}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except GeminiUnavailable as exc:
                    text, model, error = None, None, f"HTTP {exc.status}"

            def replay(_: dict, text: str | None = text) -> str:
                if text is None:
                    raise GeminiUnavailable(503, [])
                return text

            result = run_guide(answers, specialties, names, words, replay)
            outcome = Outcome(case, result.emergency, result.specialty, result.reason, model, error)
            outcomes.append(outcome)
            if model:
                models[model] += 1
            print(("ok   " if outcome.correct else "MISS ") + describe(outcome))

    t = totals(outcomes)
    print(
        f"\nRed-flag recall {t.red_caught}/{t.red_cases} ({pct(t.red_recall)}), "
        f"false alarms {t.false_alarms}/{t.ordinary}, "
        f"specialty accuracy {t.specialty_right}/{t.ordinary} ({pct(t.specialty_accuracy)})"
    )
    if not args.no_write:
        out = args.eval_dir / "symptoms_results.md"
        out.write_text(results_markdown(outcomes, models, date.today()), encoding="utf-8")
        print(f"Wrote {out}")
    return 0 if t.red_recall in (None, 1.0) and not t.unanswered else 2


if __name__ == "__main__":
    sys.exit(main())
