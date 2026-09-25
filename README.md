# MedWise BD

**Quality-first generic medicine recommender for Bangladesh.**
Search a brand or photograph a prescription, and see every brand with the same generic, strength
and dosage form, ranked by manufacturer quality (80%) and price (20%), with the reasons for each rank.

- **Live app:** https://medwise-bd.vercel.app
- **API docs:** https://medwise-bd.onrender.com/docs

> **Sample data.** All prices, quality values and interactions are sample data for this
> competition MVP, not official DGDA data. Brand names are fictional. MedWise BD does not give
> medical advice. Consult your doctor or pharmacist before changing any medicine.

## Features

| Feature | What it does |
|---|---|
| **Search** | Brand or generic name, typo-tolerant, in English or Bangla (e.g. সেফিক্সিম → Cefixime) |
| **Ranked alternatives** | Same generic + strength + dosage form only, scored out of 100 with human-readable reasons |
| **Prescription scan** | Gemini reads **only** medicine names and strengths; the user confirms every match before results. Photos are never stored |
| **Interaction checker** | Recorded interactions between any medicines, most severe first, plus a warning when two brands contain the same generic |

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
row and field if anything is invalid.

## Deployment

| Service | Settings |
|---|---|
| **Neon** | Postgres database (Singapore region) |
| **Render** (web service) | Build: `pip install -r backend/requirements.txt && python backend/scripts/import_data.py` · Start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` · Env: `DATABASE_URL`, `GEMINI_API_KEY`, `PYTHON_VERSION=3.11.9` · Health check: `/api/health` |
| **Vercel** | Root directory `frontend` · Env: `API_URL=https://medwise-bd.onrender.com` |

The free Render instance sleeps after 15 minutes idle; the first request then takes about a minute.
Open the site shortly before a demo.
