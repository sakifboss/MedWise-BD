# MedWise BD

**Quality-first generic medicine recommender for Bangladesh.**
Search a brand or photograph a prescription, and see every brand with the same generic, strength
and dosage form, ranked by manufacturer quality (80%) and price (20%), with the reasons for each rank.

- **Live app:** https://medwise-bd.vercel.app
- **API docs:** https://medwise-bd.onrender.com/docs

> **Data status.** Manufacturer quality data (stringent-regulator plant approvals, exports,
> market share) is **real and sourced**: every manufacturer lists its `source_urls`. Brands and
> prices are real MRPs from Arogga (checked 2026-11-03, each brand links its product page) and
> interactions come from DDInter. Medicine information (uses, side effects, precautions) is
> condensed from the NHS website, and from the US FDA label for cefixime; each generic links its source. MedWise BD does not give medical
> advice. Consult your doctor or pharmacist before changing any medicine.

## Features

| Feature | What it does |
|---|---|
| **Search** | Brand or generic name, typo-tolerant, in English or Bangla (e.g. সেফিক্সিম → Cefixime) |
| **Ranked alternatives** | Same generic + strength + dosage form only, scored out of 100 with human-readable reasons |
| **Prescription scan** | Gemini reads **only** medicine names and strengths; the user confirms every match before results. Photos are never stored |
| **Interaction checker** | Recorded interactions between any medicines, most severe first, plus a warning when two brands contain the same generic |
| **Savings calculator** | Enter the amount on your prescription; each brand shows its monthly cost and saving. The app never suggests a dose |
| **Prescription cost summary** | Monthly total for your brands vs the best-ranked and the cheapest brands, for every scanned medicine |
| **Bangla and English** | One tap switches the whole app, including ranking reasons and reviewed Bangla medicine information |
| **Voice search** | Say a medicine name in Bangla or English (browser speech recognition; no audio reaches MedWise) |
| **Share for the pharmacist** | WhatsApp / share / print with a QR code; a whole prescription becomes a `/share` link (nothing stored) |
| **Manufacturer pages** | Each company's regulator approvals, score breakdown, unknowns, sources and brands |
| **Installable app** | Add to the home screen like an app; shows an offline page without internet |

## How ranking works

```
Q     = 0.30·Certification + 0.25·Exports + 0.20·Compliance + 0.15·(1 − Recall history) + 0.10·Market trust
P     = 1 − (price − min) / (max − min)          (1 when all prices are equal)
Score = 100 · (0.8·Q + 0.2·P)
```

Quality factors are normalised across all manufacturers; price is normalised within the compared
group. All weights live in one place: [`backend/app/services/ranking.py`](backend/app/services/ranking.py).

## Architecture

```
Browser ──► Vercel (Next.js frontend) ──/api/*──► Render (FastAPI backend) ──► Neon (Postgres)
                                                          └──► Google Gemini (prescription reading only)
```

| Folder | Stack |
|---|---|
| [`frontend/`](frontend/) | Next.js 16 (App Router, TypeScript), Tailwind CSS, shadcn/ui |
| [`backend/`](backend/) | Python 3.11, FastAPI, SQLAlchemy, Pydantic, rapidfuzz |
| [`data/seed/`](data/seed/) | The only source of medicine data. See its [README](data/seed/README.md) for the format |

## Run with Docker

The quickest way to run everything (Postgres, backend, frontend) on your own machine:

```bash
docker compose up --build
```

Open http://localhost:3000 (API docs at http://localhost:8000/docs). The backend loads
`data/seed` into a local Postgres on every start, so it never touches the production database.
For prescription scanning, put `GEMINI_API_KEY=...` in `backend/.env` first (optional; everything
else works without it). Stop with `Ctrl+C`, or `docker compose down` if started with `-d`.

## Run locally

```bash
# Backend (http://localhost:8000)
cd backend
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # add GEMINI_API_KEY for prescription scanning
python scripts/import_data.py                         # load data/seed into the database
uvicorn app.main:app --reload

# Frontend (http://localhost:3000), in a second terminal
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Tests

```bash
cd backend && pytest                                  # ranking, search, OCR (mocked), API, import
cd frontend && npm run lint && npm run typecheck && npm run build
```

GitHub Actions runs all of these on every push, with the backend tests on both SQLite and Postgres.

## Replacing sample data with official data

Put new files with the same format in `data/seed/` and push. No code changes are needed.
The backend re-imports on every deploy, and the import stops with a clear error listing file,
row and field if anything is invalid. The import drops and recreates the medicine tables, so
column changes reach the deployed database automatically.

## Collecting real data

**Manufacturer quality** (`manufacturers.json`, `quality_factors.json`) is already real:

- `stringent_approvals`: regulators (US FDA, UK MHRA, EU GMP, TGA Australia) that approved at
  least one of the company's plants. This is plant-level, not product-level.
- `compliance_score`: 100 minus 15 per documented adverse finding by a stringent regulator in
  the last 5 years.
- `recall_data_available: false` everywhere, since no structured recall database exists for
  Bangladesh; the app says "Recall history not available" instead of claiming a clean record.
- `market_share`: IQVIA figures as reported in public summaries; estimates are explained in the
  file's `meta.note`.

**Brands and prices:** fill `data/templates/brands_template.csv` (one row per brand, with the
page the price came from), then from `backend/`:

```bash
python scripts/build_brands_from_csv.py ../data/templates/brands_template.csv
python scripts/import_data.py --dry-run
```

**Interactions:** download every `ddinter_downloads_code_*.csv` from
https://ddinter.scbdd.com/download/ into `data/raw/ddinter/`, then from `backend/`:

```bash
python scripts/extract_ddinter.py ../data/raw/ddinter
python scripts/import_data.py --dry-run
```

DDInter is licensed CC BY-NC-SA 4.0 (non-commercial, attribution required).

**Bangla medicine information:** `data/templates/generics_bn.csv` has one row per line of
English medicine text with a draft Bangla translation. A Bangla speaker checks each row and
writes `yes` in `approved` (Excel or Google Sheets, saved as CSV). Then from `backend/`:

```bash
python scripts/build_generics_bn.py apply ../data/templates/generics_bn.csv
python scripts/import_data.py --dry-run
```

A section (e.g. side effects) switches to Bangla only when every one of its lines is approved;
until then it is shown in English with a "translation under review" note. After the English
text changes, run `python scripts/build_generics_bn.py export ../data/templates/generics_bn.csv`
to add rows for the new text; changed rows are flagged as stale instead of being shown.

## Deployment

| Service | Settings |
|---|---|
| **Neon** | Postgres database (Singapore region) |
| **Render** (web service) | Build: `pip install -r backend/requirements.txt && python backend/scripts/import_data.py` · Start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` · Env: `DATABASE_URL`, `GEMINI_API_KEY`, `FRONTEND_SHARED_SECRET`, `PYTHON_VERSION=3.11.9` · Health check: `/api/health` |
| **Vercel** | Root directory `frontend` · Env: `API_URL=https://medwise-bd.onrender.com`, `FRONTEND_SHARED_SECRET` |

`FRONTEND_SHARED_SECRET` must be the same long random value on Vercel and Render. The frontend adds
it to prescription uploads, and the backend refuses uploads without it, so nobody can use up the
Gemini quota by calling the backend directly. `/api/health` shows `"frontend_secret": "set"` once
the backend has it.

The free Render instance sleeps after 15 minutes idle; the first request then takes about a minute.
Open the site shortly before a demo.
