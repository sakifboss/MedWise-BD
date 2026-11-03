# MedWise BD

Quality-first generic medicine recommender for Bangladesh.
Input: a brand name or prescription photo. Output: same-generic, same-strength
alternatives ranked by manufacturer quality (80%) and price (20%), with a reason for each rank.

This is a competition MVP (deadline 2026-11-05). All seed data is real and sourced: manufacturer
quality (regulator/company pages), brands and prices (Arogga MRP), medicine information (NHS, FDA
label for cefixime) and interactions (DDInter). Official DGDA data can replace any file later.

## Stack
- frontend/: Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui
- backend/: Python 3.11, FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL (SQLite allowed for local dev)
- Search: rapidfuzz + Postgres pg_trgm; Bangla -> Latin transliteration for Bangla input
- Prescription OCR: Gemini vision API (key in backend/.env as GEMINI_API_KEY)

## Folder structure
```
medwise-bd/
  frontend/
  backend/
    app/
      api/        # routers: search, generics, alternatives, interactions, prescription
      core/       # config, db
      models/     # SQLAlchemy models
      schemas/    # Pydantic schemas
      services/   # search.py, ranking.py, interactions.py, ocr.py
    scripts/
      import_data.py
      build_brands_from_csv.py   # data/templates/brands_template.csv -> brands.json
      extract_ddinter.py         # data/raw/ddinter/*.csv (gitignored) -> interactions.json
    tests/
  data/
    seed/         # manufacturers.json, generics.json, brands.json, quality_factors.json, interactions.json
    templates/    # brands_template.csv (team brand + price sheet)
```

## Data rules (important)
- ALL data enters the DB only through `backend/scripts/import_data.py` reading `data/seed/*.json`.
- Never hardcode medicine data in application code.
- Swapping sample data for official data must need zero code changes: same schema, new files.
- The import script validates every row and reports errors clearly.
- Every seed file says in `meta` whether it is sample (`is_sample`) and where it came from (`source`).
- Real data carries its source: manufacturers have `source_urls`, brands have a price `source_url`.
- While any dataset is sample, the UI shows a small "Sample data" tag naming what is sample.
- DDInter data is CC BY-NC-SA 4.0: credit DDInter wherever interactions are shown.

## Data model
- manufacturers(id, name, stringent_approvals, export_countries, export_country_count, regulated_market_exports, compliance_score, recall_count, recall_data_available, market_share|null, years_active, source_urls)
- generics(id, name, drug_class, indications, dosage_forms, side_effects, precautions, source_urls)
- brands(id, name, generic_id, manufacturer_id, strength, dosage_form, price_per_unit, source_url)
- interactions(id, generic_a_id, generic_b_id, severity[minor|moderate|major], description)

## Ranking formula (backend/app/services/ranking.py)
Normalise each factor to 0-1.
Q = 0.30*C + 0.25*E + 0.20*R + 0.15*(1-H) + 0.10*M
  C = approved stringent regulators / 4 (US FDA, UK MHRA, EU GMP, TGA Australia; plant-level)
  E = export footprint, R = compliance_score / 100 (absolute), H = normalised recall history,
  M = market trust (unknown market share counts as 0)
P = 1 - (price - min_price) / (max_price - min_price)   (P = 1 if all prices equal)
Final = 100 * (0.8*Q + 0.2*P)
- Only compare brands with the SAME generic, SAME strength, SAME dosage form.
- Weights live in one config dict, not scattered.
- Return a human-readable `reasons` list per brand (e.g. "Has plant(s) approved by US FDA, EU GMP").
- Never claim "No recall on record" when recall data is unavailable; say "Recall history not available".
- Unit tests required for ranking.py.

## Medical safety rules
- The LLM/vision model ONLY extracts medicine names + strengths from prescription images. It never generates dosage, indications or medical advice.
- All medicine information shown to users comes from the database.
- Extracted medicines are shown to the user for confirmation before results.
- Every results page shows: "Consult your doctor or pharmacist before changing any medicine."
- Do not store uploaded prescription images.

## Coding conventions
- Backend: type hints everywhere, small functions, pytest for tests.
- Frontend: TypeScript strict, server components where possible, mobile-first responsive design.
- Keep API responses consistent: `{ data, error }`.
- Before big changes, propose a plan and wait for approval.
- After finishing a task, run tests / lint and report results.

## Commands
- Backend: `cd backend && uvicorn app.main:app --reload`
- Tests: `cd backend && pytest`
- Import data: `cd backend && python scripts/import_data.py`
- Frontend: `cd frontend && npm run dev`

## Roadmap (approved 2026-11-03)
Work ONE step at a time: build -> tests, ruff, lint, typecheck, build -> commit + push -> verify the
live deploy -> tick the box here -> stop for the user's review before starting the next step.

- [x] **0. Real generics.json.** Replace sample indications, side effects and precautions with
  sourced text (public drug labels); add source links per generic, shown on the generic page.
  When no dataset is sample, the "Sample data" tag goes away.
- [ ] **1. Savings calculator.** On the alternatives page the user enters how many units a day
  their prescription says; each card shows monthly cost and "Save Tk X/month" vs their medicine.
  The app never suggests a dose; the number comes only from the user.
- [ ] **2. Prescription cost summary.** After confirming scanned medicines: monthly total for the
  current brands vs best-quality picks vs cheapest picks (same generic, strength and form only).
- [ ] **3. Bangla UI toggle.** All UI text in one en/bn dictionary, language kept in a cookie,
  server components stay server-rendered. Medicine data from the DB is not translated.
- [ ] **4. Bangla voice search.** Mic button using the browser Web Speech API (`bn-BD`, then `en`);
  hidden when the browser does not support it. Audio is not sent to our backend or stored.
- [ ] **5. Share for the pharmacist.** Share the chosen alternatives (WhatsApp / native share) and a
  print view with a QR code back to the page. Includes the doctor/pharmacist disclaimer.
- [ ] **6. Manufacturer transparency page.** `/manufacturers/[id]`: each approval, export and market
  data, score breakdown, every source link, and what is not known (recall data).
- [ ] **7. Installable app (PWA).** Manifest, icons, theme colour; installs from the browser.

Not doing (by design): AI chat or medicine advice (breaks the safety rules), counterfeit
detection (no reliable data), dose reminders (out of scope).
