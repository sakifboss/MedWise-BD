# Seed data

The **only** data source for the database. Load with `cd backend && python scripts/import_data.py`
(add `--dry-run` to validate without writing).

> **All current files are SAMPLE data.** Prices, quality values and interactions are illustrative,
> not official DGDA data. Brand names are fictional. Manufacturer quality values are placeholders
> and do not describe the real companies.

To switch to official data, replace these files with new ones using the same format. No code changes are needed.

## File format

Every file is `{ "meta": {...}, "records": [...] }`.

`meta`: `dataset` (must match the file name), `source`, `is_sample`, optional `sample_fields` and `note`.

Rows reference each other **by name** (case-insensitive), not by id. Unknown fields are rejected.

| File | Record fields |
|---|---|
| `manufacturers.json` | `name`, `years_active`, `export_countries[]` |
| `quality_factors.json` | `manufacturer`, `who_gmp` (bool), `regulated_market_exports` (count of regulated markets), `compliance_score` (0-100), `recall_count`, `market_share` (percent, 0-100) |
| `generics.json` | `name`, `drug_class`, `indications[]`, `dosage_forms[]`, `side_effects[]`, `precautions[]` |
| `brands.json` | `name`, `generic`, `manufacturer`, `strength`, `dosage_form`, `price_per_unit` (BDT) |
| `interactions.json` | `generic_a`, `generic_b`, `severity` (`minor` / `moderate` / `major`), `description` |

`quality_factors.json` is merged into the `manufacturers` table on import. Each manufacturer needs exactly one entry.

## Validation rules

- Strength is normalised to one format (`500MG` → `500 mg`, `120mg/5mL` → `120 mg/5 ml`), so brands
  with the same strength compare as equal.
- A brand's `dosage_form` must be listed in its generic's `dosage_forms`.
- Duplicate names, duplicate brands and duplicate interaction pairs (in either order) are rejected.
- Any error stops the import and nothing is written. Every error is listed with its file, row index and field.
