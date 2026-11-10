# Seed data

The **only** data source for the database. Load with `cd backend && python scripts/import_data.py`
(add `--dry-run` to validate without writing).

> **Manufacturer and quality files are real, sourced data** (collected 2026-11-03; see each
> record's `source_urls` and each file's `meta.note`). `brands.json` holds real brands and
> MRPs from Arogga (each row's `source_url`), built from `data/templates/brands_template.csv`.
> `interactions.json` comes from DDInter (CC BY-NC-SA 4.0). `generics.json` text is condensed from
> NHS medicine pages (cefixime, famotidine, levocetirizine: US FDA labels on DailyMed; vildagliptin:
> EMA product information); each record lists its `source_urls`. See the main README, "Collecting real data".
> `pharmacies.json` and `sylhet_areas.json` come from OpenStreetMap (© OpenStreetMap contributors,
> ODbL 1.0) through `backend/scripts/fetch_osm_pharmacies.py`; see the main README, "Pharmacy finder".

To switch to official data, replace these files with new ones using the same format. No code changes are needed.

## File format

Every file is `{ "meta": {...}, "records": [...] }`.

`meta`: `dataset` (must match the file name), `source`, `is_sample`, optional `sample_fields` and `note`.

Rows reference each other **by name** (case-insensitive), not by id. Unknown fields are rejected.

| File | Record fields |
|---|---|
| `manufacturers.json` | `name`, `years_active`, `export_countries[]`, optional `export_country_count` (when only the number is known) |
| `quality_factors.json` | `manufacturer`, `stringent_approvals[]` (any of `US FDA`, `UK MHRA`, `EU GMP`, `TGA Australia`), `regulated_market_exports` (count of regulated markets), `compliance_score` (0-100), `recall_count`, optional `recall_data_available` (default true), `market_share` (percent, 0-100, or `null` if unknown), `source_urls[]` |
| `generics.json` | `name`, `drug_class`, `indications[]`, `dosage_forms[]`, `side_effects[]`, `precautions[]`, `source_urls[]`; optional reviewed Bangla `drug_class_bn`, `indications_bn[]`, `side_effects_bn[]`, `precautions_bn[]` (each list translates every English line; written by `build_generics_bn.py`) |
| `brands.json` | `name`, `generic`, `manufacturer`, `strength`, `dosage_form`, `price_per_unit` (BDT), optional `source_url` (price source) |
| `interactions.json` | `generic_a`, `generic_b`, `severity` (`minor` / `moderate` / `major`), `description` |
| `pharmacies.json` | `name`, optional `name_bn`, `lat`, `lon`, optional `address`, `phone`, `source` (`osm` with `osm_type` + `osm_id`, or `survey` with `surveyed_by` + `surveyed_on`), `is_partner`, optional `partner_since`, `hide_phone`. No stock fields |
| `red_flags.json` | `id`, `group` (one of the checklist groups), `text` (NHS wording), optional reviewed `text_bn`, `source_url` (an `https://www.nhs.uk/` page that says to call 999) |
| `specialties.json` | `id`, `name`, `covers` (by body area, never by disease), optional reviewed `name_bn` and `covers_bn`. `general_medicine`, `paediatrics` and `obstetrics_gynaecology` are required |
| `sylhet_areas.json` | `name`, optional `name_bn`, `lat`, `lon`, `kind`, optional `osm` (e.g. `node/264490171`) |

`quality_factors.json` is merged into the `manufacturers` table on import. Each manufacturer needs exactly one entry.

## Validation rules

- Strength is normalised to one format (`500MG` → `500 mg`, `120mg/5mL` → `120 mg/5 ml`), so brands
  with the same strength compare as equal.
- A brand's `dosage_form` must be listed in its generic's `dosage_forms`.
- Duplicate names, duplicate brands and duplicate interaction pairs (in either order) are rejected.
- Pharmacies and areas must lie inside the Sylhet city box (24.86,91.82 – 24.95,91.93). A repeated
  OSM id, or two pharmacies with the same name within 20 m, is rejected. Only phone numbers that may
  be shown are stored: OSM numbers unless `hide_phone`, survey numbers only for partners.
- Any error stops the import and nothing is written. Every error is listed with its file, row index and field.
