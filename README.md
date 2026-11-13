# MedWise BD

**Quality-first generic medicine recommender for Bangladesh.**
Search a brand or photograph a prescription, and see every brand with the same generic, strength
and dosage form, ranked by manufacturer quality (80%) and price (20%), with the reasons for each rank.

- **Live app:** https://medwise-bd.vercel.app
- **API docs:** https://medwise-bd.onrender.com/docs

> **Data status.** Manufacturer quality data (stringent-regulator plant approvals, exports,
> market share) is **real and sourced**: every manufacturer lists its `source_urls`. Brands and
> prices are real MRPs from Arogga (checked 2026-11-03, 2026-11-10 and 2026-11-13, each brand links
> its product page) and interactions come from DDInter. Medicine information (uses, side effects, precautions,
> how to take) is condensed from the NHS website; from US FDA labels for cefixime, famotidine and
> levocetirizine; and from the EMA product information for vildagliptin. Each generic links its
> source. MedWise BD does not give medical advice. Consult your doctor or pharmacist before changing any medicine.

## Features

| Feature | What it does |
|---|---|
| **Search** | Brand or generic name, typo-tolerant, in English or Bangla (e.g. সেফিক্সিম → Cefixime) |
| **Ranked alternatives** | Same generic + strength + dosage form only, scored out of 100 with human-readable reasons |
| **Prescription scan** | An OpenAI vision model reads **only** medicine names and strengths; the user confirms every match before results. Photos are never stored |
| **Interaction checker** | Recorded interactions between any medicines, most severe first, plus a warning when two brands contain the same generic |
| **Same-price notice** | When every brand in a group costs the same, the page says so: the top-ranked one costs nothing extra |
| **Savings calculator** | Enter the amount on your prescription; each brand shows its monthly cost and saving. The app never suggests a dose |
| **Prescription cost summary** | Monthly total for your brands vs the best-ranked and the cheapest brands, for every scanned medicine |
| **Bangla and English** | One tap switches the whole app, including ranking reasons and reviewed Bangla medicine information |
| **Voice search** | Say a medicine name in Bangla or English (browser speech recognition; no audio reaches MedWise) |
| **Share for the pharmacist** | WhatsApp / share / print with a QR code; a whole prescription becomes a `/share` link (nothing stored) |
| **Manufacturer pages** | Each company's regulator approvals, score breakdown, unknowns, sources and brands |
| **My Medicines** | Save medicines on your phone only (MedWise never receives the list): see each one's rank and the top-ranked option, check interactions across them, add daily reminders to your calendar (.ics) and back up the list |
| **Symptom guide** | `/symptoms`: an NHS emergency checklist first (any tick: “Call 999 now” with tap-to-call), then which kind of doctor to start with and a short note for that doctor, written from your answers. Never a diagnosis, never a medicine |
| **Pharmacy finder (Sylhet)** | On every ranking page, the 10 nearest pharmacies in Sylhet city from OpenStreetMap, with distance, “Call” when a number is listed and “Directions”. Your location stays in the browser (or pick your area). We never claim a shop has a medicine: “Call before you go” |
| **Recently viewed** | The last 8 ranking and alternatives pages you opened, on the home page; kept on your phone only (no prices), with Clear |
| **Report a problem** | “Report a problem” on each brand card (wrong price, not sold any more, wrong manufacturer, other); only the brand, the reason and the day are stored, so the team can fix the data |
| **Request a medicine** | When we have no data for a medicine (search or scan), one tap asks us to add it. Only the medicine name, where it came from and the day are stored |
| **Light / dark theme, larger text** | From the header's Display menu: System (follows the phone), Light or Dark, and Normal or Large text; remembered on the device, printing always light and normal size |
| **For doctors (Rx Pad, Sylhet pilot)** | `/doctor`: doctor accounts with profile and up to 3 chambers; MedWise BD checks the BMDC registration before the verified badge shows. `/doctor/rx` writes and prints an A4 prescription with MedWise data beside the doctor. Patients' information is never stored or sent |
| **Installable app** | Add to the home screen like an app |
| **Offline mode** | Pages you open are saved; “Save all medicines for offline use” saves every medicine and ranking page. Without internet the saved copy opens with “Showing data saved on …”, and search lists the saved medicines. Online, pages are always fresh |

## How ranking works

```
Q     = 0.30·Certification + 0.25·Exports + 0.20·Compliance + 0.15·(1 − Recall history) + 0.10·Market trust
P     = cheapest price / price                    (1 for the cheapest; twice the price scores 0.5)
Score = 100 · (0.8·Q + 0.2·P)
```

Quality factors are normalised across all manufacturers. Price is compared with the cheapest brand
in the same group, so a brand that costs a little more loses only a little: Tk 6 against a
cheapest Tk 5 still scores 0.83 on price. All weights live in one place: [`backend/app/services/ranking.py`](backend/app/services/ranking.py).

## Architecture

```
Browser ──► Vercel (Next.js frontend) ──/api/*──► Render (FastAPI backend) ──► Neon (Postgres)
                                                          └──► OpenAI (prescription reading, symptom guide)
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
For prescription scanning and the symptom guide's AI step, put `OPENAI_API_KEY=...` in
`backend/.env` first (optional; everything else works without it, and the symptom guide falls back
to the person's own words). Stop with `Ctrl+C`, or `docker compose down` if started with `-d`.

## Run locally

```bash
# Backend (http://localhost:8000)
cd backend
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # add OPENAI_API_KEY for prescription scanning
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
cd frontend && npm run lint && npm run typecheck && npm test && npm run build   # npm test: Vitest, src/lib helpers
```

GitHub Actions runs all of these on every push, with the backend tests on both SQLite and Postgres.

Backend dependencies are pinned to exact versions in `backend/requirements.txt` (runtime) and
`requirements-dev.txt` (pytest, ruff), including the packages they pull in. Render, Docker and CI
therefore install the same code. CI installs with `--no-deps` and runs `pip check`, so a missing or
clashing pin fails the build. To upgrade, change the version, run the tests and push.

Dependabot opens weekly update PRs (pip, npm, GitHub Actions, Docker images) and security
fixes as soon as an advisory appears. The Audit workflow runs `pip-audit` and `npm audit` on every
push and daily: anything that ships to the browser or server must be clean, and the build-only
tools (eslint, shadcn CLI, openapi-typescript) may not have high or critical issues.

## Brand codes and migrations

Every brand has a stable **code** (`BR00042`) in `data/seed/brands.json`. Database ids change
whenever the import rebuilds the seed tables, so everything that must keep working after a deploy
uses the code:

- page links: `/alternatives/BR00042` (an old `/alternatives/<id>` link still opens, and the
  address bar then shows the code URL without reloading);
- share links: `/share?m=c:BR00042:2` (old `b:<id>` links still open);
- My Medicines (format version 2) and Recently viewed (version 2) on the phone. Lists saved
  before codes existed are matched to codes on the device with the public brand index (by brand,
  strength and form; the old id only as a fallback); a brand that is no longer listed is kept and
  marked, so nothing the user saved is lost.

`build_brands_from_csv.py` keeps a brand's code while its name, manufacturer, strength and form stay
the same (a price change keeps it), gives new brands the next number, and moves the codes of
removed brands to `meta.retired_codes`; the import refuses duplicate or retired codes.
`GET /api/brands/index` lists every brand with its code, price, check date, rank in its group and
approvals (about 43 KB, 3 KB compressed, cached for an hour).

**Durable tables** (the request log and data reports; doctor accounts later) change only through
Alembic migrations in `backend/migrations/`. `import_data.py` runs `alembic upgrade head` first and
prints only row counts before and after (for example `medicine_requests 4 -> 4`), stops if rows
would disappear, and then rebuilds the seed tables as before. Render and Docker need no extra
command. Revision 0001 creates the two tables only when they are missing, so on an existing
database it changes nothing; 0002 adds `data_reports.brand_code`. Before a release with a new
migration, make a Neon branch as a backup.

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

DDInter lists interactions for medicines taken by mouth or injection. `data/seed/dosage_forms.json`
gives each dosage form a route (`systemic` or `local`); when every catalog brand of a generic is a
local form (eye drops, cream, mouthwash, ...), the script leaves out that generic's pairs and says
so, the import rejects any such pair, and the app shows "Interactions not shown: DDInter lists them
for <generic> taken by mouth or injection, and MedWise lists only <form> for it." Add a brand in a
form taken by mouth or injection, re-run the script, and the pairs come back.

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

## Offline mode

[`frontend/public/sw.js`](frontend/public/sw.js) is network first: with internet every page and
GET `/api/*` answer is fresh, and a copy is saved with the time it was saved. Without internet the
copy is served with a `<meta name="medwise-saved-at">`, and the page shows “You're offline.
Showing data saved on …. Prices may have changed.” Next.js files under `/_next/static/` are cache
first (their names hold a hash). Never saved: non-GET requests, search, health, prescription
reading, the request log, Next.js navigation data (`?_rsc`) and non-200 answers. A saved page
keeps the headers it came with, so its Content-Security-Policy nonce still matches its scripts.
At most 100 saved pages and 300 static files; the oldest go first. Bump `VERSION` in `sw.js`
(and `PAGES_CACHE` in `src/lib/offline.ts`; a unit test checks they match) to start fresh.

## Symptom guide

`/symptoms` never diagnoses and never names a disease or a medicine. It only says which kind of
doctor to start with.

1. **Emergency checklist, no AI.** [`data/seed/red_flags.json`](data/seed/red_flags.json): signs
   copied word for word from NHS pages that say to call 999 (items that name a disease are left
   out). Ticking any of them shows a full-screen “Call 999 now or go to the nearest hospital
   emergency department.” with tap-to-call 999; the only way on is back to the checklist.
2. **The person's own words** (Bangla, Banglish or English), since when, how bad, age group and
   pregnancy (not asked for children). Before sending, the page says the text goes to OpenAI,
   which does not use it to train its models and may keep it for up to 30 days to check for abuse.
3. **`POST /api/symptom-guide`** asks OpenAI (same client and model fallback as prescription
   reading, `app/services/llm.py`) for JSON matching a strict schema: a specialty id from
   [`data/seed/specialties.json`](data/seed/specialties.json), `red_flag_suspected` and a short
   note. The server then:
   - uses the fallback (general medicine specialist, note built from the person's own answers)
     when the answer is not valid JSON, has extra keys or names an unknown specialty;
   - drops an AI note that names a medicine or generic from our catalog (Bangla too), a dose, or a
     word from [`backend/app/core/symptom_words.json`](backend/app/core/symptom_words.json)
     (diagnosis words; edit it without code changes);
   - shows the emergency screen when the model suspects an emergency, even in an invalid answer:
     the model can add a warning, never remove one;
   - sends children to paediatrics and pregnancy to obstetrics and gynaecology, whatever the model says.
4. **Result:** the specialty, and the note (editable), labelled “Written from your answers. Not a
   diagnosis.”, optionally with the My Medicines list from the phone, to share or print. The
   shared link is the plain `/symptoms` page; the note is never put in a URL.

Nothing the person writes is stored or logged by MedWise BD. Only our frontend may call the
endpoint (shared secret), 10 an hour per device and 200 a day overall.

**Bangla** for the checklist and specialties goes through `data/templates/symptoms_bn.csv`:

```bash
cd backend
python scripts/build_symptoms_bn.py export ../data/templates/symptoms_bn.csv   # new or changed text
python scripts/build_symptoms_bn.py apply ../data/templates/symptoms_bn.csv    # approved rows only
```

**Evaluation:** `python scripts/eval_symptoms.py` runs 40 invented cases (`data/eval/symptoms.json`,
en, bn and Banglish) through the whole pipeline with the real OpenAI API and writes
[`data/eval/symptoms_results.md`](data/eval/symptoms_results.md). Red-flag recall must be 100%.
Latest (OpenAI gpt-6-luna, 2026-11-13): red flags 13/13, false alarms 0/27, specialty 27/27,
the same as with Gemini before.

## Pharmacy finder (Sylhet)

[`data/seed/pharmacies.json`](data/seed/pharmacies.json) and `sylhet_areas.json` come from
OpenStreetMap (© OpenStreetMap contributors, ODbL 1.0), credited under the list and in the footer.
Refresh them from `backend/`:

```bash
python scripts/fetch_osm_pharmacies.py          # Overpass API, Sylhet city box 24.86,91.82 – 24.95,91.93
python scripts/import_data.py --dry-run
```

The fetch keeps `amenity=pharmacy` with a name, leaves out homeopathic, herbal, Ayurvedic and Unani
shops (by name or tag) and prints every excluded entry with its reason. Kept by hand and carried
over a re-fetch: `is_partner`, `partner_since` (a partner who agreed; consent forms stay with the
team) and `hide_phone` (hide a number when the owner asks). Team survey rows (`source: "survey"`,
recorded on site with a phone's GPS, with `surveyed_by` and `surveyed_on`) are added to the same
file; their phone is shown only for partners. The import rejects places outside the box, a repeated
OSM id, and two pharmacies with the same name within 20 m.

`GET /api/pharmacies?city=sylhet` returns the whole list and takes no position: the browser asks
for location only after the tap and sorts by straight-line distance on the device. If location is
denied or outside Sylhet, the user picks an area. The list never says what a shop has in stock.
Each row shows the shop's street address when OSM has a real one; when the address is empty or
only says "Sylhet" / "সিলেট", it shows "Near <closest area>" (from `sylhet_areas.json`, by the
shop's coordinates) next to the distance.

## Reports about a brand's data

“Report a problem” on each brand card sends only the brand id and one fixed reason (`wrong_price`,
`not_sold`, `wrong_manufacturer`, `other`); there is no free text. The backend stores those, the day
and the brand's own details (name, manufacturer, strength, form, because brand ids change when the
seed import rebuilds the tables): no IP address, user agent, cookie or user id. Like the request log,
the `data_reports` table has its own metadata (the import never drops it), only our frontend may
send reports, 10 an hour per device and 1000 a day. There is no public list; the team reads it with

```bash
cd backend
python scripts/top_reports.py --database-url "postgresql://..."   # brands with the most reports
```

and fixes the seed files (for prices: `data/templates/brands_template.csv`).

## Medicine requests

"Request this medicine" stores only the text (trimmed, at most 80 characters), its source
(`search` or `prescription`) and the day: no IP address, user agent, cookie or user id. Only our
frontend may send requests, with a limit per device (10 an hour) and overall (1000 a day). The
`medicine_requests` table has its own SQLAlchemy metadata, so the seed import, which drops and
recreates the medicine tables on every deploy, never touches it. There is no public list; read it
with:

```bash
cd backend
python scripts/top_requests.py --database-url "postgresql://..."   # 30 most requested
```

## Doctor accounts (Rx Pad)

`/doctor` (sign up and log in), `/doctor/profile`, `/doctor/account` and the public
`/doctor/privacy`. Only what the doctor types about themselves is stored (durable tables, Alembic
0003): email, a scrypt password hash, profile, up to 3 chambers, hashed login tokens and hashed
one-time reset tokens. Never anything about patients. Logins end after 12 hours without use or 7
days; the `mw_doc` cookie is HttpOnly, SameSite=Lax, Path=/api/doctor (other requests, such as
search, never carry it), Secure except on http://localhost. Changes need
our frontend's secret header and an Origin listed in `SITE_ORIGINS` (default: the live site and
http://localhost:3000; no Vercel previews). Five failed
logins for an email, or 20 from one client, wait 15 minutes; 5 sign-ups or resets an hour per
client. Responses are `Cache-Control: no-store` and the service worker never touches doctor pages.

**Writing a prescription** (`/doctor/rx`): patient details, complaints, findings, diagnosis,
allergies, up to 12 medicine lines (catalog brands with rank, price and approvals; catalog
generics; or names not in MedWise), tests, advice and follow-up. Each line gets a patient
instruction in Bangla and English made only from what the doctor typed (no dose is ever
suggested), the total for tablets and capsules, and an approx. cost (Arogga MRP, on screen only).
Warnings for the doctor (never blocking): DDInter interactions (only generic ids are sent), the
same generic twice, and lines MedWise cannot check. "Print / Save as PDF" prints an A4
prescription with the letterhead, the chosen chamber, a signature line, page numbers and the
DEMO or not-verified mark. Patient details stay in the browser tab and on the paper: they are
never stored (no local storage, cookies or IndexedDB) and never sent; patient fields turn off
autofill, browser spellcheck and translation, and have no voice input. Search sends only the
typed text, at most 60 searches a minute per tab. The only thing the pad keeps on the device is
the doctor's choice of print language (localStorage `medwise.rxPrefs`; Bangla at first).

Accounts start as pending. The owner manages them on their own computer (no admin pages):

```bash
cd backend
python scripts/doctors.py --prod list --status pending
python scripts/doctors.py --prod verify 12        # confirm each check: BMDC register, identity
python scripts/doctors.py --prod reject 12 --reason "..."
python scripts/doctors.py --prod reset-link 12    # one-time link, 60 minutes; send after a phone check
python scripts/doctors.py --prod create-demo --email demo@example.com --name "Dr. Demo"
python scripts/doctors.py --prod delete 12
```

`--prod` reads `PROD_DATABASE_URL` from `backend/.env`; without it the script uses `DATABASE_URL`.
Facts on the privacy page (data region, restore window, contact) live in
`frontend/src/lib/doctor-config.ts`.

## Deployment

| Service | Settings |
|---|---|
| **Neon** | Postgres database (Singapore region) |
| **Render** (web service) | Build: `pip install -r backend/requirements.txt && python backend/scripts/import_data.py` · Start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` · Env: `DATABASE_URL`, `OPENAI_API_KEY`, `FRONTEND_SHARED_SECRET`, `PYTHON_VERSION=3.11.17` (same as `.python-version` and the Dockerfile) · Health check: `/api/health` |
| **Vercel** | Root directory `frontend` · Env: `API_URL=https://medwise-bd.onrender.com`, `FRONTEND_SHARED_SECRET` |

**OpenAI** (prescription reading and the symptom guide) is a paid API: keep the key only in
`backend/.env` and on Render (never in git or chat), and set a monthly usage limit in the OpenAI
dashboard. Requests use the Responses API with `store: false` and a strict JSON schema. Each
feature has its own model setting, chosen by measurement (`data/eval/`):

| Feature | Setting (default) | Fallback setting (default) | Why | Cost per call |
|---|---|---|---|---|
| Prescription reading | `OPENAI_OCR_MODEL` (`gpt-6.1-terra`) | `OPENAI_OCR_FALLBACK_MODELS` (`gpt-6-luna`) | real handwriting: 94.1% recall vs 70.6% | ~$0.0034 |
| Symptom guide | `OPENAI_MODEL` (`gpt-6-luna`) | `OPENAI_FALLBACK_MODELS` (`gpt-6.1-terra`) | already 13/13 red flags, 27/27 specialties | ~$0.0001 |

`OPENAI_REASONING_EFFORT` (default `low`) applies to both. The daily limits (300 prescriptions,
about $1 at most; 200 symptom guides) also cap the spend.

`FRONTEND_SHARED_SECRET` must be the same long random value on Vercel and Render. The frontend adds
it to prescription uploads and symptom guide requests, and the backend refuses them without it,
so nobody can spend the OpenAI budget by calling the backend directly. `/api/health` shows `"frontend_secret": "set"` once
the backend has it.

The free Render instance sleeps after 15 minutes idle; the first request then takes about a minute.
Open the site shortly before a demo.
