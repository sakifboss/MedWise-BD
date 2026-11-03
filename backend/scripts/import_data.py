"""Load data/seed/*.json into the database. This is the ONLY way data enters the DB.

Every row is validated first, and references between files are checked. If anything
is wrong, all errors are reported and nothing is written. On success, the existing
data is replaced in a single transaction.

Usage (from backend/):
    python scripts/import_data.py                 # validate, then replace all data
    python scripts/import_data.py --dry-run       # validate only
    python scripts/import_data.py --data-dir ../data/official --database-url postgresql+psycopg://...
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, ValidationError  # noqa: E402
from rapidfuzz import process  # noqa: E402
from sqlalchemy import Engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, make_engine  # noqa: E402
from app.models import Brand, Generic, Interaction, Manufacturer  # noqa: E402
from app.schemas.seed import (  # noqa: E402
    BrandSeed,
    GenericSeed,
    InteractionSeed,
    ManufacturerSeed,
    QualityFactorSeed,
    SeedMeta,
)

RowT = TypeVar("RowT", bound=BaseModel)

SEED_SCHEMAS: dict[str, type[BaseModel]] = {
    "manufacturers": ManufacturerSeed,
    "quality_factors": QualityFactorSeed,
    "generics": GenericSeed,
    "brands": BrandSeed,
    "interactions": InteractionSeed,
}


@dataclass
class SeedData:
    manufacturers: list[ManufacturerSeed] = field(default_factory=list)
    quality_factors: list[QualityFactorSeed] = field(default_factory=list)
    generics: list[GenericSeed] = field(default_factory=list)
    brands: list[BrandSeed] = field(default_factory=list)
    interactions: list[InteractionSeed] = field(default_factory=list)
    sample_datasets: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    sample_datasets: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------- loading


def _row_label(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    if "name" in raw:
        return f" '{raw['name']}'"
    if "manufacturer" in raw:
        return f" '{raw['manufacturer']}'"
    if "generic_a" in raw:
        return f" '{raw.get('generic_a')} + {raw.get('generic_b')}'"
    return ""


def _format_validation_error(prefix: str, exc: ValidationError) -> list[str]:
    messages = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"]) or "(row)"
        messages.append(f"{prefix} -> {location}: {err['msg']}")
    return messages


def _read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{path.name}: file not found at {path}")
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON at line {exc.lineno}, column {exc.colno}")
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        errors.append(f"{path.name}: expected an object with 'meta' and a 'records' list")
        return None
    return doc


def load_dataset(
    data_dir: Path, dataset: str, schema: type[RowT], errors: list[str]
) -> tuple[SeedMeta | None, list[RowT]]:
    """Validate one seed file. Invalid rows are reported and skipped."""
    path = data_dir / f"{dataset}.json"
    doc = _read_json(path, errors)
    if doc is None:
        return None, []

    meta: SeedMeta | None = None
    try:
        meta = SeedMeta.model_validate(doc.get("meta"))
        if meta.dataset != dataset:
            errors.append(
                f"{path.name} -> meta.dataset: expected '{dataset}', got '{meta.dataset}'"
            )
    except ValidationError as exc:
        errors.extend(_format_validation_error(f"{path.name} meta", exc))

    rows: list[RowT] = []
    for index, raw in enumerate(doc["records"]):
        try:
            rows.append(schema.model_validate(raw))
        except ValidationError as exc:
            prefix = f"{path.name}[{index}]{_row_label(raw)}"
            errors.extend(_format_validation_error(prefix, exc))
    return meta, rows


def load_seed_data(data_dir: Path, errors: list[str]) -> SeedData:
    data = SeedData()
    for dataset, schema in SEED_SCHEMAS.items():
        meta, rows = load_dataset(data_dir, dataset, schema, errors)
        setattr(data, dataset, rows)
        if meta is not None and meta.is_sample:
            data.sample_datasets.append(dataset)
    return data


# ---------------------------------------------------------------- cross-file checks


def _key(name: str) -> str:
    return name.casefold()


def _unknown(kind: str, name: str, known: list[str]) -> str:
    message = f"unknown {kind} '{name}'"
    match = process.extractOne(name, known, score_cutoff=80) if known else None
    return f"{message} (did you mean '{match[0]}'?)" if match else message


def _check_unique_names(file: str, names: list[str], errors: list[str]) -> None:
    seen: set[str] = set()
    for index, name in enumerate(names):
        if _key(name) in seen:
            errors.append(f"{file}[{index}] '{name}': duplicate name")
        seen.add(_key(name))


def _check_quality_factors(data: SeedData, errors: list[str]) -> None:
    manufacturer_names = [m.name for m in data.manufacturers]
    known = {_key(n) for n in manufacturer_names}
    covered: set[str] = set()
    for index, row in enumerate(data.quality_factors):
        label = f"quality_factors.json[{index}] '{row.manufacturer}'"
        if _key(row.manufacturer) not in known:
            errors.append(
                f"{label}: {_unknown('manufacturer', row.manufacturer, manufacturer_names)}"
            )
        elif _key(row.manufacturer) in covered:
            errors.append(f"{label}: duplicate quality factors for this manufacturer")
        covered.add(_key(row.manufacturer))
    for name in manufacturer_names:
        if _key(name) not in covered:
            errors.append(f"manufacturers.json '{name}': no entry in quality_factors.json")


def _check_brands(data: SeedData, errors: list[str]) -> None:
    generic_names = [g.name for g in data.generics]
    manufacturer_names = [m.name for m in data.manufacturers]
    forms_by_generic = {_key(g.name): g.dosage_forms for g in data.generics}
    known_manufacturers = {_key(n) for n in manufacturer_names}
    seen: set[tuple[str, str, str, str]] = set()

    for index, row in enumerate(data.brands):
        label = f"brands.json[{index}] '{row.name}'"
        forms = forms_by_generic.get(_key(row.generic))
        if forms is None:
            errors.append(f"{label}: {_unknown('generic', row.generic, generic_names)}")
        elif row.dosage_form not in forms:
            errors.append(
                f"{label}: dosage form '{row.dosage_form}' not listed for generic "
                f"'{row.generic}' (allowed: {', '.join(forms)})"
            )
        if _key(row.manufacturer) not in known_manufacturers:
            errors.append(
                f"{label}: {_unknown('manufacturer', row.manufacturer, manufacturer_names)}"
            )

        identity = (_key(row.name), _key(row.manufacturer), row.strength, row.dosage_form)
        if identity in seen:
            errors.append(f"{label}: duplicate brand ({row.strength} {row.dosage_form})")
        seen.add(identity)


def _check_interactions(data: SeedData, errors: list[str]) -> None:
    generic_names = [g.name for g in data.generics]
    known = {_key(n) for n in generic_names}
    seen: set[frozenset[str]] = set()
    for index, row in enumerate(data.interactions):
        label = f"interactions.json[{index}] '{row.generic_a} + {row.generic_b}'"
        for name in (row.generic_a, row.generic_b):
            if _key(name) not in known:
                errors.append(f"{label}: {_unknown('generic', name, generic_names)}")
        pair = frozenset({_key(row.generic_a), _key(row.generic_b)})
        if len(pair) == 1:
            errors.append(f"{label}: a generic cannot interact with itself")
        elif pair in seen:
            errors.append(f"{label}: duplicate pair (order does not matter)")
        seen.add(pair)


def check_references(data: SeedData, errors: list[str]) -> None:
    _check_unique_names("manufacturers.json", [m.name for m in data.manufacturers], errors)
    _check_unique_names("generics.json", [g.name for g in data.generics], errors)
    _check_quality_factors(data, errors)
    _check_brands(data, errors)
    _check_interactions(data, errors)


# ---------------------------------------------------------------- writing


def _clear_tables(session: Session) -> None:
    for model in (Interaction, Brand, Generic, Manufacturer):
        session.execute(delete(model))


def _insert_manufacturers(session: Session, data: SeedData) -> dict[str, int]:
    quality = {_key(q.manufacturer): q for q in data.quality_factors}
    rows = []
    for m in data.manufacturers:
        q = quality[_key(m.name)]
        rows.append(
            Manufacturer(
                name=m.name,
                years_active=m.years_active,
                export_countries=m.export_countries,
                export_country_count=m.export_country_count,
                stringent_approvals=q.stringent_approvals,
                regulated_market_exports=q.regulated_market_exports,
                compliance_score=q.compliance_score,
                recall_count=q.recall_count,
                recall_data_available=q.recall_data_available,
                market_share=q.market_share,
                source_urls=q.source_urls,
            )
        )
    session.add_all(rows)
    session.flush()
    return {_key(r.name): r.id for r in rows}


def _insert_generics(session: Session, data: SeedData) -> dict[str, int]:
    rows = [Generic(**g.model_dump()) for g in data.generics]
    session.add_all(rows)
    session.flush()
    return {_key(r.name): r.id for r in rows}


def _insert_brands(
    session: Session, data: SeedData, generic_ids: dict[str, int], manufacturer_ids: dict[str, int]
) -> None:
    session.add_all(
        Brand(
            name=b.name,
            generic_id=generic_ids[_key(b.generic)],
            manufacturer_id=manufacturer_ids[_key(b.manufacturer)],
            strength=b.strength,
            dosage_form=b.dosage_form,
            price_per_unit=b.price_per_unit,
            source_url=b.source_url,
        )
        for b in data.brands
    )


def _insert_interactions(session: Session, data: SeedData, generic_ids: dict[str, int]) -> None:
    for row in data.interactions:
        a, b = sorted((generic_ids[_key(row.generic_a)], generic_ids[_key(row.generic_b)]))
        session.add(
            Interaction(
                generic_a_id=a,
                generic_b_id=b,
                severity=row.severity,
                description=row.description,
                description_bn=row.description_bn,
            )
        )


def write_database(engine: Engine, data: SeedData) -> None:
    """Replace all medicine data in one transaction.

    The tables are dropped and recreated first: they hold only data derived from the
    seed files, and recreating them keeps an existing database in step with the models
    after a column change.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        _clear_tables(session)
        manufacturer_ids = _insert_manufacturers(session, data)
        generic_ids = _insert_generics(session, data)
        _insert_brands(session, data, generic_ids, manufacturer_ids)
        _insert_interactions(session, data, generic_ids)


# ---------------------------------------------------------------- entry points


def run_import(data_dir: Path, engine: Engine | None, dry_run: bool = False) -> ImportResult:
    result = ImportResult()
    data = load_seed_data(data_dir, result.errors)
    check_references(data, result.errors)
    result.sample_datasets = data.sample_datasets
    result.counts = {name: len(getattr(data, name)) for name in SEED_SCHEMAS}
    if result.ok and not dry_run and engine is not None:
        write_database(engine, data)
    return result


def _print_report(result: ImportResult, dry_run: bool) -> None:
    if not result.ok:
        print(f"Import FAILED: {len(result.errors)} error(s). Nothing was written.\n")
        for error in result.errors:
            print(f"  - {error}")
        return

    print("Validation passed." if dry_run else "Import complete.")
    for name, count in result.counts.items():
        print(f"  {name:<16} {count:>4} rows")
    if result.sample_datasets:
        print(f"\nNOTE: SAMPLE data in: {', '.join(result.sample_datasets)}")
    if dry_run:
        print("\nDry run: database not modified.")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Validate and import seed data.")
    parser.add_argument("--data-dir", type=Path, default=settings.seed_dir)
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--dry-run", action="store_true", help="validate only, write nothing")
    args = parser.parse_args(argv)

    engine = None if args.dry_run else make_engine(args.database_url)
    result = run_import(args.data_dir, engine, dry_run=args.dry_run)
    _print_report(result, args.dry_run)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
