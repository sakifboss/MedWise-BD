# MedWise BD

Quality-first generic medicine recommender for Bangladesh.
Input: a brand name or prescription photo. Output: same-generic, same-strength
alternatives ranked by manufacturer quality (80%) and price (20%), with a reason for each rank.

This is a competition MVP. It runs on SAMPLE data now; official DGDA data will replace it later.

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
    tests/
  data/
    seed/         # manufacturers.json, generics.json, brands.json, quality_factors.json, interactions.json
```

## Data rules (important)
- ALL data enters the DB only through `backend/scripts/import_data.py` reading `data/seed/*.json`.
- Never hardcode medicine data in application code.
- Swapping sample data for official data must need zero code changes: same schema, new files.
- The import script validates every row and reports errors clearly.
- Every price, quality value and interaction in seed data is SAMPLE. The UI shows a small "Sample data" tag.

## Data model
- manufacturers(id, name, who_gmp, export_countries, regulated_market_exports, compliance_score, recall_count, market_share, years_active)
- generics(id, name, drug_class, indications, dosage_forms, side_effects, precautions)
- brands(id, name, generic_id, manufacturer_id, strength, dosage_form, price_per_unit)
- interactions(id, generic_a_id, generic_b_id, severity[minor|moderate|major], description)

## Ranking formula (backend/app/services/ranking.py)
Normalise each factor to 0-1.
Q = 0.30*C + 0.25*E + 0.20*R + 0.15*(1-H) + 0.10*M
  C = certification (who_gmp), E = export footprint, R = compliance, H = normalised recall history, M = market trust
P = 1 - (price - min_price) / (max_price - min_price)   (P = 1 if all prices equal)
Final = 100 * (0.8*Q + 0.2*P)
- Only compare brands with the SAME generic, SAME strength, SAME dosage form.
- Weights live in one config dict, not scattered.
- Return a human-readable `reasons` list per brand (e.g. "WHO-GMP certified", "No recall on record").
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