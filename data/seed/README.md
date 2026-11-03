# Seed data

The **only** data source for the database. Load with `cd backend && python scripts/import_data.py`
(add `--dry-run` to validate without writing).

> **Manufacturer and quality files are real, sourced data** (collected 2026-11-03; see each
> record's `source_urls` and each file's `meta.note`). `generics.json`, `brands.json` and
> `interactions.json` are still SAMPLE data: brand names are fictional, prices and interaction
> severities are illustrative. See the main README, "Collecting real data".

To switch to official data, replace these files with new ones using the same format. No code changes are needed.

## File format

Every file is `{ "meta": {...}, "records": [...] }`.

`meta`: `dataset` (must match the file name), `source`, `is_sample`, optional `sample_fields` and `note`.

Rows reference each other **by name** (case-insensitive), not by id. Unknown fields are rejected.

| File | Record fields |
|---|---|
| `manufacturers.json` | `name`, `years_active`, `export_countries[]`, optional `export_country_count` (when only the number is known) |
| `quality_factors.json` | `manufacturer`, `stringent_approvals[]` (any of `US FDA`, `UK MHRA`, `EU GMP`, `TGA Australia`), `regulated_market_exports` (count of regulated markets), `compliance_score` (0-100), `recall_count`, optional `recall_data_available` (default true), `market_share` (percent, 0-100, or `null` if unknown), `source_urls[]` |
| `generics.json` | `name`, `drug_class`, `indications[]`, `dosage_forms[]`, `side_effects[]`, `precautions[]` |
| `brands.json` | `name`, `generic`, `manufacturer`, `strength`, `dosage_form`, `price_per_unit` (BDT), optional `source_url` (price source) |
| `interactions.json` | `generic_a`, `generic_b`, `severity` (`minor` / `moderate` / `major`), `description` |

`quality_factors.json` is merged into the `manufacturers` table on import. Each manufacturer needs exactly one entry.

## Validation rules

- Strength is normalised to one format (`500MG` → `500 mg`, `120mg/5mL` → `120 mg/5 ml`), so brands
  with the same strength compare as equal.
- A brand's `dosage_form` must be listed in its generic's `dosage_forms`.
- Duplicate names, duplicate brands and duplicate interaction pairs (in either order) are rejected.
- Any error stops the import and nothing is written. Every error is listed with its file, row index and field.
