# MedWise BD — frontend

Next.js 16 (App Router, TypeScript strict), Tailwind CSS 4, shadcn/ui.

## Run locally

```bash
# 1. Start the backend first (from backend/): uvicorn app.main:app --reload
# 2. Then:
cp .env.example .env.local   # API_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

Server components call the backend at `API_URL`. The browser calls same-origin `/api/*`,
which `next.config.ts` rewrites to the backend, so no CORS setup is needed.

## Pages

| Route | What it shows |
|---|---|
| `/` | Search by brand or generic name (English or Bangla) |
| `/generics/[id]` | Uses, side effects, precautions, interactions, strengths/forms to compare |
| `/generics/[id]/ranking?strength=&form=` | All brands of one strength + form, ranked |
| `/alternatives/[brandId]` | Ranked alternatives to a specific brand (the brand itself is highlighted) |

## API types

Types in `src/lib/api-schema.ts` are generated from the backend's OpenAPI schema. After
changing backend response models:

```bash
cd ../backend && python scripts/export_openapi.py   # writes ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```
