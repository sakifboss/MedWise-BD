# MedWise BD

Quality-first generic medicine recommender for Bangladesh.
Input: a brand name or prescription photo. Output: same-generic, same-strength
alternatives ranked by manufacturer quality (80%) and price (20%), with a reason for each rank.

This is a competition MVP (deadline 2026-11-05). All seed data is real and sourced: manufacturer
quality (regulator/company pages), brands and prices (Arogga MRP), medicine information (NHS; US FDA labels
for cefixime, famotidine and levocetirizine; EMA for vildagliptin) and interactions (DDInter). Official DGDA data can replace any file later.

## Stack
- frontend/: Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui
- backend/: Python 3.11, FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL (SQLite allowed for local dev)
- Search: rapidfuzz + Postgres pg_trgm; Bangla -> Latin transliteration for Bangla input
- Prescription OCR and the symptom guide: OpenAI Responses API (key in backend/.env and on Render as
  OPENAI_API_KEY; never in git or chat). Gemini was used until 2026-11-13.

## Folder structure
```
medwise-bd/
  frontend/
  backend/
    app/
      api/        # routers: search, generics, alternatives, manufacturers, interactions, prescription,
                  #          medicine_requests, stats, pharmacies, symptom_guide, data_reports, doctor
      core/       # config, db
      models/     # SQLAlchemy models
      schemas/    # Pydantic schemas
      services/   # search.py, ranking.py, interactions.py, ocr.py, llm.py (shared OpenAI client),
                  # symptom_guide.py
    scripts/
      import_data.py
      build_brands_from_csv.py   # data/templates/brands_template.csv -> brands.json
      extract_ddinter.py         # data/raw/ddinter/*.csv (gitignored) -> interactions.json
      top_requests.py            # most requested medicines (request log; no public endpoint)
      top_reports.py             # brands reported as having wrong data (no public endpoint)
      eval_ocr.py                # OCR accuracy on data/eval (see data/eval/README.md)
      fetch_osm_pharmacies.py    # OpenStreetMap (Overpass) -> pharmacies.json, sylhet_areas.json
      build_symptoms_bn.py       # Bangla review sheet for red_flags.json and specialties.json
      eval_symptoms.py           # symptom guide on data/eval/symptoms.json (red-flag recall)
      doctors.py                 # doctor accounts: list, verify, reject, reset-link, demo, delete
    tests/
  data/
    seed/         # manufacturers.json, generics.json, brands.json, quality_factors.json, interactions.json,
                  # dosage_forms.json (route of each form: systemic | local),
                  # pharmacies.json, sylhet_areas.json (OpenStreetMap, ODbL),
                  # red_flags.json (NHS), specialties.json
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
- DDInter is for medicines taken by mouth or injection. When every catalog brand of a generic is a
  local form (route "local" in dosage_forms.json: eye/ear drops, eye ointment, cream, ointment, gel,
  mouthwash), extract_ddinter.py leaves out its pairs and reports them, the import rejects any
  such pair, and every place that shows interactions says instead: "Interactions not shown: DDInter
  lists them for <generic> taken by mouth or injection, and MedWise lists only <form> for it."
  Adding a brand in a form taken by mouth or injection and re-running the extraction brings them back.

## Data model
- manufacturers(id, name, stringent_approvals, export_countries, export_country_count, regulated_market_exports, compliance_score, recall_count, recall_data_available, market_share|null, years_active, source_urls)
- generics(id, name, drug_class, indications, dosage_forms, side_effects, precautions, source_urls)
- brands(id, code (stable, BR + 5 digits), name, generic_id, manufacturer_id, strength, dosage_form,
  price_per_unit, source_url, price_checked_on, aliases (other written names, e.g. "Mycetin"))
- dosage_forms(id, name, route[systemic|local])
- Durable (Alembic, never dropped): medicine_requests(id, query, source, requested_on),
  data_reports(id, brand_id, brand_code, brand_name, manufacturer, strength, dosage_form, reason, reported_on),
  doctors(id, email, password_hash (scrypt$N$r$p$salt$hash), display_name, display_name_bn, degrees,
  specialty, bmdc_number, phone, status[pending|verified|rejected], rejection_reason, verified_at,
  verified_by, verify_method, is_demo, created_at, last_login_day), doctor_chambers(id, doctor_id,
  position, name, address, hours, phone), doctor_sessions(id, token_hash (sha256), doctor_id,
  created_at, last_seen, expires_at), doctor_password_resets(id, token_hash, doctor_id, expires_at,
  used_at)
- interactions(id, generic_a_id, generic_b_id, severity[minor|moderate|major], description)
- pharmacies(id, name, name_bn, lat, lon, address, phone (only when it may be shown), source[osm|survey],
  osm_type, osm_id, is_partner, partner_since); areas(id, name, name_bn, lat, lon). No stock data.
- red_flags(id, key, group, text, text_bn, source_url); specialties(id, key, name, name_bn, covers, covers_bn)

## Ranking formula (backend/app/services/ranking.py)
Normalise each factor to 0-1.
Q = 0.30*C + 0.25*E + 0.20*R + 0.15*(1-H) + 0.10*M
  C = approved stringent regulators / 4 (US FDA, UK MHRA, EU GMP, TGA Australia; plant-level)
  E = export footprint, R = compliance_score / 100 (absolute), H = normalised recall history,
  M = market trust (unknown market share counts as 0)
P = min_price / price   (1 for the cheapest brand, and 1 when all prices are equal; twice the price = 0.5)
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
- Rx Pad: the app never proposes a medicine, dose, frequency, duration, test or diagnosis, and
  patient information never reaches our backend (Phase 5 rules).

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
- Everything in Docker (Postgres + backend + frontend): `docker compose up --build`, then http://localhost:3000.
  The frontend's /api rewrite is fixed at build time, so the image gets API_URL as a build arg.

## Roadmap (approved 2026-11-03)
Work ONE step at a time: build -> tests, ruff, lint, typecheck, build -> commit + push -> verify the
live deploy -> tick the box here -> stop for the user's review before starting the next step.

- [x] **0. Real generics.json.** Replace sample indications, side effects and precautions with
  sourced text (public drug labels); add source links per generic, shown on the generic page.
  When no dataset is sample, the "Sample data" tag goes away.
- [x] **1. Savings calculator.** On the alternatives page the user enters how many units a day
  their prescription says; each card shows monthly cost and "Save Tk X/month" vs their medicine.
  The app never suggests a dose; the number comes only from the user.
- [x] **2. Prescription cost summary.** After confirming scanned medicines: monthly total for the
  current brands vs best-quality picks vs cheapest picks (same generic, strength and form only).
- [x] **3. Bangla and English, everywhere.** Search already accepts Bangla. Add an en/bn toggle
  (cookie) covering: all UI text (one dictionary), ranking `reasons` (backend templates per language),
  and medicine information (`*_bn` fields in generics.json, entered through the seed import like all
  data). Bangla medicine text is a translation drafted by Claude and approved line by line by a
  Bangla-speaking team member; the page says it is translated and links the English source.
  Brand and manufacturer names stay as printed on packs.
  Done 2026-11-04: all 304 lines of generics_bn.csv approved by the team and applied. When
  English medicine text changes, run `build_generics_bn.py export`, re-review, then `apply`.
- [x] **4. Bangla voice search.** Mic button using the browser Web Speech API (`bn-BD`, then `en`);
  hidden when the browser does not support it. Audio is not sent to our backend or stored.
- [x] **5. Share for the pharmacist.** Share the chosen alternatives (WhatsApp / native share) and a
  print view with a QR code back to the page. Includes the doctor/pharmacist disclaimer.
- [x] **6. Manufacturer transparency page.** `/manufacturers/[id]`: each approval, export and market
  data, score breakdown, every source link, and what is not known (recall data).
- [x] **7. Installable app (PWA).** Manifest, icons, theme colour; installs from the browser.

Not doing (by design): AI diagnosis or medicine suggestions, AI chat about medicines, dose advice,
counterfeit detection (no reliable data). The P10 symptom guide is allowed only because it never
names a disease or a medicine. The Rx Pad (Phase 5) prints only what the doctor typed.

## Security hardening (approved 2026-11-04)
Same workflow as the roadmap: one step at a time; tests, ruff, lint, typecheck, build; for anything
that touches the frontend, rerun the browser test suites (a too-strict CSP breaks pages silently);
commit + push -> verify live -> tick the box -> stop for the user's review.

Already in place: HTTPS + HSTS (Vercel), CORS closed to other origins, uploads checked by file
bytes and size and never stored, OCR rate limits (per client + global daily cap), no secrets in
git history, non-root Docker images, Next.js patched to 16.4.2.

- [x] **S1. Security headers.** Frontend: nonce-based Content-Security-Policy set per request in
  `frontend/src/proxy.ts`, plus frame-ancestors/X-Frame-Options, nosniff, Referrer-Policy,
  Permissions-Policy (microphone for voice search, geolocation for the P9 pharmacy finder), no X-Powered-By. Backend: nosniff,
  frame denial and a locked-down CSP on API responses (not on /docs).
- [x] **S2. Only our frontend may call the prescription endpoint** (and, since P10, the symptom guide). The Next proxy adds a secret
  header (`FRONTEND_SHARED_SECRET`, set on Vercel and Render) to /api/prescription; the backend
  rejects OCR requests without it, so nobody can drain the OpenAI budget by calling Render directly.
- [x] **S3. Rate limits on search and interactions,** generous for people, blocking floods.
- [x] **S4. Pin backend dependencies** (exact versions installed by Render, Docker and CI).
  Every package, including transitive ones, is pinned with `==`; CI and Docker install with
  `--no-deps` + `pip check`, so the list must stay complete.
- [x] **S5. Dependency watch:** Dependabot (npm, pip, GitHub Actions, Docker) and audits in CI;
  move the `shadcn` CLI to devDependencies (not needed at runtime).
  `.github/workflows/audit.yml` (push + daily): pip-audit on the pins; `npm audit --omit=dev`
  must be clean, the full tree may have nothing high. Remaining moderates are in eslint and the
  shadcn CLI only (dev tools, npm's only "fix" is a downgrade).

## Dependency updates (Dependabot PRs, started 2026-11-04)
One step at a time, same workflow: CI + Audit green, browser suites for anything the app ships,
merge -> verify live -> tick -> stop for review. Revert with `git revert` if live breaks.

- [x] **D1. GitHub Actions** (#1 setup-python 7, #2 checkout 7, #6 setup-node 7): CI-only, merged.
- [x] **D2. Declined majors closed** (#4 TypeScript 7, #5 eslint 10, #7 @types/node 26), with
  ignore rules in `.github/dependabot.yml` so they do not come back.
- [x] **D3. Frontend group** (#3: React 19.3, Next 16.4.3, lucide, base-ui, cn 0.5).
  cn 0.5 gives identical output to 0.4 on every class string in the app; all browser suites
  passed on the PR build and live.
- [x] **D4. Backend group** (#9/#10: fastapi 0.162 and 17 more; fastapi now needs opentelemetry-api,
  which must be pinned too, or `pip check` fails). Applied on main with that pin; 199 tests,
  pip-audit, live smoke test and browser suites passed.
- [x] **D5. Python 3.11.17** (#8) in Docker, CI (`.python-version`) and Render (`PYTHON_VERSION`)
  together. Done in 3ea17b4; the owner set PYTHON_VERSION=3.11.17 on Render. Render's env var
  wins over `.python-version`, so change both when upgrading Python.

Owner-only (user's accounts): restrict the Gemini key to the Generative Language API and set a
budget alert; 2FA on GitHub, Vercel, Render and Neon; rotate the Neon password if it was ever
shared; turn on Dependabot alerts in the GitHub repo settings.
Done by the owner 2026-11-04.

## Roadmap phase 2 (approved 2026-11-09)
Same workflow as the roadmap above, one step at a time: plan first and wait for the user's OK ->
build -> tests, ruff, lint, typecheck, build (and the browser test suites for frontend changes) ->
commit + push -> verify the live deploy -> tick the box here -> stop for the user's review.

Rules for every step:
- Every user-facing string exists in en and bn (dictionaries.ts; bn must match the shape of en).
  Bangla drafts below are suggestions; keep the app's existing wording style.
- No medical advice, ever: the app never suggests a dose, a different generic, or a medicine for a
  symptom. It only shows facts from cited sources.
- Medicine data enters the database only through data/seed/*.json and import_data.py.
  The P5 request log is the only exception, and it never becomes medicine data.
- When behaviour changes, update README.md, this file and the "How ranking works" text.
- Never hard-code counts (generics, brands, interactions) in UI text; read them from the data.

- [x] **P1. Price score = min_price / price.**
  In backend/app/services/ranking.py replace the min-max price score with
  P = min_price / price (1.0 for the cheapest brand, and 1.0 when all prices are equal).
  Update the module docstring, the formula in this file, and test_ranking.py (price_score cases and
  the hand-worked A/B/C example). Real-data check after import, Omeprazole 20 mg capsule:
  Losectil 88.5, Seclo 87.5, Proceptin 83.2 (Seclo moves from 3rd to 2nd). In Esomeprazole 20 mg
  the top pick changes from Maxpro to Nexum MUPS; this is expected (quality first).
  Done 2026-11-10 (9632211): verified live in en and bn. 13 of 25 groups changed order and 7 changed
  their top pick (both Esomeprazole groups, Pantoprazole, both Metformin groups, Gliclazide,
  Atorvastatin 10 mg).

- [x] **P2. Same-price banner.**
  When every brand in a compared group (same generic, strength and dosage form) has the same price
  per unit, the ranking page and the alternatives page show one banner above the list:
  en "All these brands cost the same (Tk X per unit). The top-ranked one costs nothing extra."
  bn "এই সবগুলো ব্র্যান্ডের দাম একই (প্রতি ইউনিট ৳X)। তালিকার প্রথমটি নিতে কোনো বাড়তি খরচ নেই।"
  Use the app's existing price/number formatting. Hide it when the group has only one brand.
  Prefer computing it from data the page already has; add an API field only if needed.
  Today 7 of 25 groups qualify (e.g. Paracetamol 500 mg, Losartan 50 mg, Cetirizine 10 mg).
  Tests: unit test for the all-equal check; check one equal-price and one mixed-price page.
  Done 2026-11-10 (f035cf6): 8 of 25 groups qualify (also Amoxicillin 125 mg/5 ml, Aspirin 75 mg,
  Metronidazole 400 mg, Paracetamol 120 mg/5 ml, Amoxicillin 500 mg); Warfarin 5 mg has one brand.
  Helper src/lib/same-price.ts (Vitest); verified live on all 25 ranking pages in en and bn.

- [x] **P3. OCR accuracy evaluation.**
  Goal: a measured accuracy number for the competition document and video.
  Add backend/scripts/eval_ocr.py and data/eval/README.md (how to add images, how to run).
  Input: data/eval/prescriptions/<name>.jpg|png|webp, each with <name>.json ground truth:
  {"medicines": [{"name": "Seclo", "strength": "20 mg"}, ...]} = what a careful human reads on the
  prescription (name as written; strength when written, else null).
  Privacy: data/eval/prescriptions/ and data/eval/cache/ are gitignored (real prescriptions hold
  personal data). Only data/eval/README.md and data/eval/results.md are committed, and results.md
  contains no patient or doctor names, only file ids and medicine names.
  Run: the real GeminiExtractor (needs GEMINI_API_KEY), then match_prescription against a
  temporary SQLite database loaded from data/seed with run_import. Cache each image's raw
  extraction in data/eval/cache/ so re-runs do not call Gemini again; --refresh forces a new call.
  Wait between calls to stay inside free-tier limits.
  Metrics:
  1. Reading: an extracted medicine is correct when its name matches a ground-truth name
     (rapidfuzz ratio >= 85 after lowercasing; configurable) and, when both have a strength, the
     strengths are equal after normalize_strength. Report recall (correct / ground truth) and
     precision (correct / extracted).
  2. Matching: of the ground-truth medicines that exist in our catalog, how many the app matched
     to the right generic + strength.
  Print per-image misses and totals; write data/eval/results.md with date, image count, models
  used and totals. Unit tests for the scoring code with fake extractions (no network).
  Done 2026-11-10: 23 images (10 real handwritten, 10 synthetic printed, 3 degraded copies).
  Real handwritten: reading recall 82.4%, precision 82.4%; matching 11/15 pre-selected right,
  12/15 offered. Overall recall 87.5%. The first-choice model was busy (503), so the fallback
  gemini-3.5-flash-lite read 22 of 23; re-run with --refresh to measure the first choice.
  Scoring also ignores dosage-form words, accepts a bare number for a strength, and skips reads
  of lines nobody could read (`unreadable` in the image's json). Photos are resized like the app.

- [x] **P4. "How to take" from the label.**
  Add optional how_to_take (list of short lines) and how_to_take_bn per record in generics.json,
  through schema, model, import, API and the generic page (section "How to take" /
  "কীভাবে খাবেন", with the source link under it). Content: only what the generic's existing
  source_urls (NHS page or FDA label) say about timing with meals, milk/dairy, alcohol, or other
  things to take apart from it. Keep the source's wording. If the source says nothing, leave the
  field empty and hide the section. Never write our own advice, doses or durations.
  Draft English for all generics by reading the cited pages. Bangla goes through the existing
  review sheet: extend build_generics_bn.py so export/apply include the new field; the team
  approves every line before apply.
  Done 2026-11-10 (d0286a1): 59 lines for 20 generics, each verbatim from the cited NHS page or
  FDA label (checked by script); no doses (a test checks). Ibuprofen line 1 is shortened (dose
  removed); metformin has no meal line because the source ties it to a dose. Bangla approved
  by the owner and applied; all five fields are Bangla for all 20 generics. Verified live.

- [x] **P5. "Request this medicine".**
  When search finds nothing, and when a scanned medicine cannot be matched, show
  en "We cover N medicines so far." + button "Request this medicine"; after the click
  en "Thanks — this helps us choose what to add next."
  bn "এখন পর্যন্ত আমরা Nটি ওষুধ কভার করি।" / "এই ওষুধটি যোগ করার অনুরোধ করুন" /
  "ধন্যবাদ — পরে কোন ওষুধ যোগ করব, তা ঠিক করতে এটি কাজে লাগবে।" (N comes from the data.)
  Backend: POST /api/requests {query, source: "search" | "prescription"} stores only the trimmed
  query (max 80 chars), the source and the date (day only). No IP, no user agent, no cookie, no
  user id. Rate-limit per client with the existing RateLimiter (about 10 per hour). Call it the
  same way the frontend already calls search; keep the CSP and security headers working.
  IMPORTANT: import_data.py drops and recreates all tables on every deploy. The requests table
  must survive that: give it its own SQLAlchemy MetaData/Base (or make the import drop only the
  seed tables), and add a test that run_import leaves existing request rows untouched.
  Read-out: backend/scripts/top_requests.py prints the 30 most requested queries with counts
  (run locally with DATABASE_URL). No public endpoint lists requests.
  Done 2026-11-10: table medicine_requests on RequestsBase (own metadata); also GET /api/stats
  for catalog counts; frontend-only, 10/hour per client and 1000/day overall. Verified live:
  a 'Fexo' request sent through the site survived the redeploy of 1487f27 (top_requests.py).

- [x] **P6. Offline mode for saved pages.**
  Today frontend/public/sw.js only shows offline.html and never caches data, on purpose, so prices
  stay fresh. Change it, keeping freshness first:
  - Network-first for GET page navigations and the Next.js data requests those pages make. On a
    200 response, save a copy. When the network fails, serve the saved copy; if none, offline.html.
  - Pages served from the cache show a banner: en "You're offline. Showing data saved on <date>.
    Prices may have changed." bn "আপনি অফলাইনে আছেন। <date>-এ সংরক্ষিত তথ্য দেখানো হচ্ছে।
    দাম বদলে থাকতে পারে।"
  - A "Save all medicines for offline use" button (home page or footer) that pre-fetches every
    generic page and every ranking page, with a done message. Search needs internet: when offline,
    say so and list the saved medicines instead.
  - Never cache POST requests, /api/prescription, the request log, or non-200 responses.
    Cap the cache (about 100 entries, oldest out) and bump the cache name.
  - Make sure cached pages still work with the nonce-based CSP.
  Update the comment at the top of sw.js and the README.
  Test in Chrome DevTools offline mode: a saved ranking page loads with the banner; an unsaved page
  shows offline.html; back online, fresh data loads.
  Done 2026-11-10 (2de06d2): caches v2 (pages 100, static 300); /_next/static and app icons cache
  first; saved pages keep their headers (CSP nonce matches) and get a medwise-saved-at <meta>;
  'Save all' (footer) saves 45 pages via GET /api/generics. Verified in Chrome offline mode
  locally and live: banner en/bn, offline.html for unsaved pages, fresh online, offline search
  list, never-saved requests, cap trimming, no CSP violations.

- [x] **P7. Eight more generics (data step).**
  Add: Fexofenadine, Ketotifen, Domperidone, Famotidine, Levocetirizine, Rosuvastatin, Bisoprolol,
  Vildagliptin. For each, use the strength and dosage form with the most brands on Arogga.
  Warfarin 5 mg has only one brand: add brands, or drop the group if no second brand is found.
  1. Generic records: same rules as roadmap step 0 (sourced text, source_urls, keep the source's
     wording). Sources in order: NHS medicine page, then the US FDA label on DailyMed, then the EMA
     product information (e.g. vildagliptin has no FDA label). Fill how_to_take as in P4.
  2. Bangla: through the review sheet; the team approves before apply.
  3. Brands and prices: add the new groups to data/templates/brands_template.csv for the team to
     fill (Arogga MRP + page link, only the manufacturers in manufacturers.json), then run
     build_brands_from_csv.py and fix any reported rows.
  4. Interactions: re-run extract_ddinter.py with the DDInter CSVs in data/raw/ddinter/; extend
     DDINTER_ALIASES if DDInter spells a name differently; report generics it could not find.
  5. import_data.py --dry-run must pass. Update every count in README.md and this file.
  Done 2026-11-10: Ketotifen replaced by Loratadine (no NHS, FDA or EMA source for oral ketotifen);
  Bisoprolol 2.5 mg (tie with 5 mg); Warfarin 5 mg dropped (one brand). Now 28 generics, 188 brands,
  32 compared groups, 55 interactions. Sources: NHS (5), DailyMed (Famotidine: Teva; Levocetirizine:
  Xyzal OTC + Glenmark Rx), EMA (Vildagliptin/Galvus). All 20 how_to_take lines verbatim (script).
  Bangla approved by the owner (31 lines reuse approved translations). DDInter file C was missing
  before, so 4 existing pairs (e.g. Amlodipine + Atorvastatin) were missing too; now added.
  DDInter has no data for Domperidone, Gliclazide or Vildagliptin (not US-approved).
  Brand names from Arogga: decimal strengths are now trimmed too ("Bislol 2.5" -> "Bislol").

## Phase 3 — features as pull requests (approved 2026-11-09)
All Roadmap phase 2 rules apply (en + bn for every string, no medical advice, data only through
seed files and import_data.py, no hard-coded counts, docs updated when behaviour changes).

PR workflow for every step:
1. `git switch main && git pull`, then create `feat/pN-<short-name>`.
2. Plan first and wait for the user's OK. The plan lists files, data, tests, privacy and safety.
3. Small, focused commits. Run tests, ruff, lint, typecheck, build, and the browser test suites.
4. Push the branch and open a PR with `gh pr create`. If gh is missing or not logged in, push and
   give the user the compare link plus the PR title and body to paste.
5. PR body: what and why; each new screen described in en and bn; how to test (Vercel preview for
   frontend-only PRs; `docker compose up` for PRs with backend changes, because previews use the
   production API); privacy (what is stored, where, for how long); safety (how it obeys the
   no-medical-advice rule); what is not done. Tick this step's box in the PR's last commit.
6. Never merge. Wait for green CI and the user's review. After the user merges, verify the live
   deploy and report.

- [x] **P8. My Medicines (on this device only).**
  Frontend-only. New page /my-medicines ("My Medicines" / "আমার ওষুধ"), linked in the header.
  Storage: on the device only, through one module (frontend/src/lib/my-medicines.ts) with a
  versioned format; every read/write in try/catch; the page still works, with a message, when
  storage is unavailable. Nothing about the list is sent to our backend; the page only calls the
  existing public ranking and interaction APIs.
  Saved item: brand id, brand name, generic, strength, dosage form, optional units per day (entered
  by the user, same rule as the savings calculator), optional reminder times, date added. No photos,
  no names of people, no conditions.
  Saving: "Save to My Medicines" on the alternatives page (the user's own brand and each card) and
  "Save all to My Medicines" on prescription results. Saving the same brand twice updates it.
  For each saved medicine show: its current rank in its group; the top-ranked brand if different,
  with the price difference per 30 units (per month when units per day is set, using the existing
  savings helpers); "Same price, higher-ranked option" when prices are equal. Always add
  "Ask your doctor or pharmacist before changing." Never say "switch".
  Interaction check across all saved medicines with the existing interaction API, major first,
  with the DDInter credit.
  Reminders: the user enters times per medicine; the app never suggests times. "Add to calendar"
  downloads one .ics file made on the device, with daily repeating events (RRULE:FREQ=DAILY) in
  floating local time. Option "Hide medicine names in the calendar" (title becomes
  "Medicine reminder" / "ওষুধের রিমাইন্ডার").
  Backup: "Download my list" (JSON), "Import list" (validated), "Delete all" (with confirm).
  Privacy note on the page: en "Saved only on this phone. MedWise BD never receives this list."
  bn "শুধু এই ফোনে সংরক্ষিত। MedWise BD এই তালিকা কখনো পায় না।"
  No login in this PR. Tests: keep logic in pure helpers (storage format and migration, .ics
  text, rank comparison) and unit-test them; if the frontend has no unit test runner, add Vitest
  as a dev dependency for lib/ helpers only.
  Done 2026-11-10 (PR): localStorage key medwise.myMedicines, format version 1 (lib/my-medicines.ts),
  .ics in lib/ics.ts; 20 Vitest cases; browser test checks that no request carries the list.

- [x] **P9. Sylhet pharmacy finder (real locations, no stock claims).**
  Data first, then stop for the user:
  1. backend/scripts/fetch_osm_pharmacies.py queries the Overpass API for amenity=pharmacy (nodes
     and ways; ways use their centre) inside Sylhet city (confirm the bounding box in the plan,
     roughly 24.86,91.82 to 24.95,91.93), plus place=suburb/neighbourhood nodes for area names.
     It writes data/seed/pharmacies.json: name, name_bn if present, lat, lon, address and phone
     if present, osm_type, osm_id; meta: source "OpenStreetMap contributors", licence ODbL,
     fetched date. Report how many pharmacies, how many have a name, how many have a phone. STOP.
  2. If there are fewer than about 30 named pharmacies, propose a team survey: rows in
     data/templates/pharmacies_template.csv recorded on site with a phone's GPS (never copied
     from Google Maps), with surveyor and date. Survey rows are real places the team visited.
  Partners: fields is_partner and partner_since. A phone number from the survey is shown only
  for partners who agreed. Consent forms stay with the team and never enter the repo.
  Backend: seed schema, model and import with validation (coordinates inside the Sylhet box, no
  duplicates by osm id, or by name within 20 m). GET /api/pharmacies?city=sylhet returns the
  whole list (it is small), rate-limited like search.
  Frontend: on the alternatives and ranking pages, "Find pharmacies near me (Sylhet)" /
  "কাছের ফার্মেসি খুঁজুন (সিলেট)". It asks for browser location; distances are computed in the
  browser and the location never leaves the device. If location is denied or outside Sylhet,
  the user picks an area from the list. Show the nearest 10: name, distance, "MedWise partner"
  badge, "Call" (tel:) when a phone is allowed, and "Directions" (opens a maps link).
  Always show: en "We don't know which medicines each shop has. Call before you go."
  bn "কোন দোকানে কোন ওষুধ আছে তা আমরা জানি না। যাওয়ার আগে ফোন করে নিন।"
  Outside Sylhet: "We cover Sylhet city for now." / "আপাতত শুধু সিলেট শহর।"
  No embedded map in this PR (the CSP stays unchanged). Attribution "© OpenStreetMap contributors"
  linking to openstreetmap.org/copyright under the list and in the footer sources.
  Tests: import validation, API, distance sorting.
  Done 2026-11-10 (PR): 49 named OSM pharmacies (0 with a phone on OSM), 20 areas; 5 left out by
  rule (1 unnamed, 4 homeopathic). Survey not needed yet (>= 30 named); Kumargaon and Subidbazar
  are 'to add by team GPS' (found on OSM and added 2026-11-13: Subid Bazar Road, and the
  Kumargaon power plant). Nobody is a partner yet. Directions open Google Maps with only the
  destination. Browser test: mocked location at Zindabazar, denied, Dhaka, en/bn; no request
  carries the location.
  Addresses that are empty or only "Sylhet" (43 + 4 of 49) show "Near <closest area>" instead.

- [x] **P10. Symptom guide (no diagnosis, no medicines).**
  Page /symptoms ("Symptom guide" / "লক্ষণ গাইড"). The top of the page says: en "This guide does
  not diagnose or suggest medicines. It helps you get the right care." bn "এই গাইড রোগ নির্ণয় বা
  ওষুধের পরামর্শ দেয় না। সঠিক চিকিৎসা পেতে সাহায্য করে।"
  Step 1, always first, no AI: an emergency checklist from data/seed/red_flags.json (text en/bn,
  group, source_url). Content only from NHS pages that say to call 999 or go to A&E (for example
  heart attack, stroke, sepsis, anaphylaxis, severe breathing difficulty, seizure); keep the
  source's wording; Bangla through the review sheet. If any item is ticked, show a full-screen
  message: en "Call 999 now or go to the nearest hospital emergency department." bn "এখনই ৯৯৯-এ
  কল করুন অথবা নিকটতম হাসপাতালের জরুরি বিভাগে যান।" with tap-to-call 999. The flow stops there.
  Step 2: the user describes the problem in free text (Bangla, Banglish or English) and fills:
  since when, how bad (mild / moderate / severe), age group (child / adult / older adult),
  pregnant (yes / no / not applicable).
  AI: POST /api/symptom-guide calls Gemini with the same client setup and model fallback as
  ocr.py. The model receives only the user's text and fields and must return JSON matching a
  strict Pydantic schema, extra keys forbidden:
  {"specialty": <id from data/seed/specialties.json>, "red_flag_suspected": bool,
   "note": {"main_problem": str (max 120), "duration": str (max 60),
            "other_symptoms": [str (max 60), at most 8]}}
  The system prompt says: do not diagnose; do not name any disease or medicine; choose a specialty
  only from the list; set red_flag_suspected to true when unsure.
  Server-side checks after the model answers:
  - Invalid JSON, extra keys or an unknown specialty: use the fallback (general medicine
    specialist, note built from the user's own fields without AI).
  - Any note text that contains a medicine or generic name from our catalog (reuse search), a dose
    pattern (mg, ml, tablet, capsule, times a day), or a word from a configurable diagnosis-word
    list: drop the AI note and use the fallback note.
  - red_flag_suspected true: show the emergency screen. The model can add a warning; it can never
    remove one.
  - Child age group always maps to paediatrics; pregnant "yes" always maps to obstetrics and
    gynaecology.
  specialties.json: id, name en/bn, what it covers en/bn (general medicine, paediatrics,
  obstetrics and gynaecology, dermatology, ENT, eye, orthopaedics, cardiology, neurology,
  psychiatry, dental). The team reviews the list, ideally with a doctor.
  Step 3 result: the specialty ("A <specialty> doctor is usually the right place to start. If you
  are unsure, start with a general medicine specialist."), the doctor note (the user can edit it
  before sharing), an option to include the user's saved My Medicines list, and share/print with
  the existing share components. Label: "Written from your answers. Not a diagnosis." /
  "আপনার উত্তর থেকে লেখা। এটি রোগ নির্ণয় নয়।"
  Privacy: before sending, say the text goes to Google's Gemini service to be processed. We never
  store or log the text (no request-body logging). Protect the endpoint like /api/prescription:
  the frontend shared-secret header and per-client plus global daily rate limits.
  Evaluation: data/eval/symptoms.json with about 40 invented test descriptions (en, bn, Banglish;
  no real patients) with the expected specialty and red-flag flag; backend/scripts/eval_symptoms.py
  reports specialty accuracy and red-flag recall. Red-flag recall must be 100% before the PR is
  ready; commit data/eval/symptoms_results.md.
  Tests: schema rejection (extra keys, unknown specialty), medicine name and dose pattern in the
  note, red-flag override, child and pregnancy rules, rate limit, shared-secret header.
  Done 2026-11-10 (PR): 30 NHS signs in 7 groups (chest pain, shortness of breath, stroke symptoms,
  anaphylaxis, epilepsy, sepsis pages; the 'When to call 999' page no longer lists symptoms), items
  naming a disease left out; 11 specialties; all Bangla approved by the owner. Free Gemini tier by the
  owner's choice: the notice says Google may keep and review the text. Eval (40 invented cases):
  red flags 13/13, false alarms 0/27, specialty 27/27. Logo text hides below 420 px so the header fits.

## Phase 4 (added 2026-11-10)
Same rules and PR workflow as Phase 3: plan first and wait for the user's OK; en + bn for every
string; no medical advice; data only through seed files and import_data.py; no hard-coded counts;
docs updated when behaviour changes; never merge (the user merges).

Pending outside this list: nothing for OpenAI (see Q6). All 188 brand prices were
re-checked against Arogga on 2026-11-13: none changed. Adding more medicines was on hold (owner,
2026-11-10) and resumes in Phase 5, step R1b.

- [ ] **Q1. "Usually keeps" from partner pharmacies (Sylhet).** Blocked until the team has at least
  one partner (consent form kept by the team, never in the repo).
  Team: about once a month, phone each partner and fill data/templates/pharmacy_stock_template.csv
  (pharmacy osm id or survey id, generic, strength, dosage form, brands they mentioned, asked_on,
  asked_by). A build script writes data/seed/pharmacy_stock.json; import_data.py checks that the
  pharmacy is a partner, the generic + strength + form is in the catalog, asked_on is not in the
  future, and reports rows older than 30 days.
  App: /api/pharmacies adds, per partner, what it usually keeps (only entries asked within the
  last 30 days, computed per request, so old entries disappear without a deploy). In the finder on
  ranking and alternatives pages:
  en "Usually keeps <generic> <strength> <form> (the shop told us on <date>)"
  bn "সাধারণত <generic> <strength> <form> রাখে (দোকান জানিয়েছে <date>)";
  "Brands they mentioned: …"; a filter "Only shops that usually keep this medicine" /
  "শুধু যে দোকান সাধারণত এই ওষুধ রাখে" (still sorted by distance); "Call before you go" stays.
  Never "in stock"; no quantities, shop prices, orders or reservations; non-partner shops get no
  medicine claims. A partner can be removed with a data change only.

- [x] **Q2. Light / dark theme.** A theme button in the header: System (default) / Light / Dark,
  remembered in a cookie (like the language), rendered on the server so there is no flash and no
  inline script (the nonce CSP stays as it is). System follows prefers-color-scheme through CSS.
  Check every page and component in both themes (contrast of badges, score bars, severity colours,
  the red emergency screen, QR code, charts), keep print always light, and set the PWA theme
  colour per theme. Browser tests for both themes and all three choices.
  Done 2026-11-11 (PR): cookie `theme` (system | light | dark), <html data-theme> from the server;
  the `dark` Tailwind variant and the dark tokens apply on screen only (print stays light).
  Text contrast measured on 10 pages: WCAG AA in both themes (light muted text darkened to 0.52).
  Header labels from md (768 px), logo text hidden below 460 px; no sideways scroll 320-1024 px.

- [x] **Q6. OpenAI instead of Gemini** (owner, 2026-11-13: paid OpenAI API, Gemini removed).
  backend/app/services/llm.py: Responses API (POST /v1/responses), strict JSON schema, store=false,
  models gpt-6-luna then gpt-6.1-terra (settings), reasoning effort low, IPv4, nothing logged,
  httpx only (no new dependency). OCR sends the photo as input_image (detail high); the symptom
  guide's schema limits the specialty to our ids; every server-side check and rule is unchanged.
  Privacy text: OpenAI does not train on API data and may keep it up to 30 days for abuse checks.
  Owner: key only in backend/.env and on Render (OPENAI_API_KEY), monthly usage limit set in the
  OpenAI dashboard; remove GEMINI_API_KEY from Render after the merge.
  Evaluations 2026-11-13: symptom guide (gpt-6-luna) red flags 13/13, false alarms 0/27, specialty
  27/27. OCR on real handwriting: gpt-6-luna recall 70.6% (worse than Gemini's 82.4%),
  gpt-6.1-terra 94.1% (data/eval/results.md); terra returns nothing for the synthetic
  pages marked "NOT A REAL PRESCRIPTION", as our instructions ask. Cost per scan: luna $0.0004,
  terra $0.0034. Owner's decision 2026-11-13: terra for scans (OPENAI_OCR_MODEL, luna as fallback),
  luna for the symptom guide (OPENAI_MODEL); the daily scan limit stays at 300 (~$1/day at most).
  data/eval/results.md shows the scan model; results_gpt-6-luna.md keeps luna for comparison.

Approved by the owner 2026-11-10 ("Q2 ok", with Q3, Q4 and Q5), built in this order, one PR each:

- [x] **Q3. Larger text.** In the same header menu as the theme ("Display" / "প্রদর্শন"): text size
  Normal / Large ("স্বাভাবিক" / "বড়"), saved in a cookie and rendered on the server like the theme.
  Large scales the root font size (about 112.5%), so every rem-based size grows; check that no page
  scrolls sideways at 320 px in en and bn, that the header still fits, and that print stays normal.
  Done 2026-11-11 (PR): two sizes (owner's choice), cookie `text` (normal | large), <html data-text>,
  112.5% on screen only. Header in Large: logo text hidden below 520 px, tight spacing below 400 px,
  language button icon-only below 360 px; the long bn 'save for offline' button wraps. No sideways
  scroll on 9 pages at 9 widths (320-1024 px) in en and bn, light and dark; contrast unchanged.

- [x] **Q4. "Report a problem" with a brand's data.** On each brand card of the ranking and
  alternatives pages: "Report a problem" / "সমস্যা জানান" with fixed reasons only: wrong price,
  not sold any more, wrong manufacturer, other ("দাম ভুল", "আর বিক্রি হয় না", "প্রস্তুতকারক ভুল",
  "অন্য কিছু"); no free text. POST /api/reports {brand_id, reason} stores only those two and the day
  (no IP, user agent, cookie or user id), in its own SQLAlchemy metadata like the request log so the
  import never drops it; frontend secret and limits like the request log (10 an hour per client,
  1000 a day). backend/scripts/top_reports.py lists reports per brand for the team, who fix the seed
  files. No public endpoint lists reports. After sending: "Thanks — we will check this brand's
  data." / "ধন্যবাদ — আমরা এই ব্র্যান্ডের তথ্য যাচাই করব।"
  Done 2026-11-11 (PR): table data_reports on RequestsBase. Besides brand_id, reason and the day it
  saves the brand's name, manufacturer, strength and form (not personal data): brand ids are
  reassigned when the import rebuilds the tables, so an id alone could later name the wrong brand.

- [x] **Q5. Recently viewed, on this device only.** The last 8 ranking or alternatives pages opened
  (medicine name, strength, form and link; no prices) kept in localStorage through one module with
  a versioned format, every read and write in try/catch; shown on the home page as "Recently
  viewed" / "সম্প্রতি দেখা" with "Clear" / "মুছে ফেলুন" and the note "Saved only on this phone." /
  "শুধু এই ফোনে সংরক্ষিত।". Nothing is sent to the backend. Vitest for the list logic.
  Done 2026-11-11 (PR): localStorage key medwise.recent, format version 1 (lib/recent.ts); stored
  links must match our ranking or alternatives page patterns; opening a page again moves it to the
  top; links carry no page state (e.g. the calculator amount).

## Phase 5 — Doctor's Rx Pad (approved 2026-11-13)
Same rules and PR workflow as Phase 3: plan first and wait for the user's OK; en + bn for every
string; no hard-coded counts; docs updated when behaviour changes; never merge (the user merges).
Order: R1 -> R1b -> R2 -> R3 -> R4 -> R5 -> (R6); each step starts after the previous one is merged.

Purpose: doctors write prescriptions with MedWise data beside them (quality rank, price, approvals,
interactions), print a clear A4 prescription, and give the patient a QR code that opens the
medicines in MedWise BD. The paper, signed by hand, stays the prescription; the QR is a helper.

Catalog decision (owner, 2026-11-13): present the Rx Pad as a Sylhet pilot now, and grow the
catalog in R1b right after R1 (the hold on adding medicines ends there).
Deadline (owner, 2026-11-13): there is time before the competition; no fixed date yet. Build the
steps in order and stop for review after each, as usual.

Rules for every R step:
- Patient information never reaches our backend. Patient name, age, sex, weight, complaints,
  findings, diagnosis, allergies, tests, advice and the medicine list exist only in the doctor's
  open browser tab and on the printed page or PDF. They are not written to localStorage,
  sessionStorage, IndexedDB or cookies, not sent in any request (URL, body or header) and never
  logged. A browser test types a unique patient name and checks every request and storage area.
- The browser itself must not keep or send patient text either: every patient field has
  autocomplete="off" (no form autofill history), spellcheck={false} (Chrome's enhanced spellcheck
  sends text to Google) and translate="no"; voice input is offered only in the medicine search,
  never in patient fields (browser speech recognition sends audio to the browser maker).
- The app never proposes a medicine, dose, frequency, duration, test or diagnosis. No default or
  pre-selected dose. Dose shortcuts are the same for every medicine and none is selected.
  Templates are written by each doctor, private to that doctor, never shared, listed, ranked or
  aggregated; the app ships no templates.
- Medicine facts come only from the database (seed files). Search suggests only names that match
  what the doctor typed.
- Same generic only: the pad may show a brand's rank among brands of the same generic, strength and
  dosage form. It never suggests a different generic.
- Doctor accounts are the only new stored personal data, exactly as listed in R2. Passwords and
  tokens are stored hashed. Nothing personal goes into logs. A public privacy and terms page for
  doctors (/doctor/privacy) says what is stored, why, where, for how long, and how to delete it.
- Demo accounts print "DEMO — not a real prescription" / "ডেমো — আসল প্রেসক্রিপশন নয়" across
  every printed page and on the /rx page. Accounts that are not verified print "Doctor not yet
  verified by MedWise BD" / "ডাক্তার এখনো MedWise BD দ্বারা যাচাই হননি".
- The QR proves who issued it, not that the medicines or doses are right, and it can be copied.
  Wording never suggests MedWise checked the medicines (see R4).
- Anything that must outlive a deploy (templates, QR codes, share links, the device-only lists of
  P8 and Q5, page links) refers to brands by the stable brand code from R1, never by a database id.
- Durable tables (request log, reports, doctor tables) change only through Alembic migrations
  (from R1). Seed tables keep drop/create in import_data.py.
- The service worker never caches /doctor/* or /api/doctor/*. Those responses send
  Cache-Control: no-store.
- DDInter data is CC BY-NC-SA 4.0 (non-commercial): fine for the competition and a free tool; any
  paid use of the Rx Pad needs a different interaction source or a licence first.

- [x] **R1. Foundations: stable brand codes, brand index, migrations.**
  1. Every record in data/seed/brands.json gets a `code` ("BR" + 5 digits, e.g. BR00042), unique
     and never reused; meta.retired_codes lists codes of removed brands. A one-time script assigns
     codes to the current brands in file order. build_brands_from_csv.py keeps a brand's code when
     name + manufacturer + strength + dosage form match an existing record (also when only the
     price changed), gives new rows the next free code, and retires codes of removed brands.
     import_data.py validates: present, unique, right format, not retired. Model, schemas and API
     responses that return brands include `code`.
  2. GET /api/brands/index: every brand with code, name, generic (en/bn), strength, dosage form,
     manufacturer, price per unit, price source date, rank in its compared group and group size,
     and number of stringent approvals (0-4). Cache-Control public, max-age 3600; rate-limited
     like search. Report its size in the plan (it must stay small enough to fetch whole).
  3. Share links: new links use codes ("c:<code>:<quantity>"); old "b:<id>" links still open.
     Vitest for encode/decode.
  4. Everything else that keeps a brand id moves to codes:
     - My Medicines (P8, localStorage medwise.myMedicines): format version 2 stores the brand code;
       a version 1 list is migrated on the device (each id looked up once in the brand index,
       while ids still match; an item that cannot be matched is kept with its name and a note).
     - Pages: /alternatives/<code> (e.g. /alternatives/BR00042); /alternatives/<id> still works and
       redirects to the code URL. Recently viewed (Q5, medwise.recent) moves to version 2 with code
       links; version 1 items are migrated the same way.
     - Data reports (Q4) already store the brand's details; also store its code from now on.
  5. Alembic for the durable tables (RequestsBase: medicine_requests, data_reports; doctor tables
     later). The first revision must run safely on the live Neon database where these tables
     already exist with rows: no data loss. Show the plan before any live run; the owner makes a
     Neon branch (backup) first. Startup (Dockerfile CMD and the Render start command) runs
     `alembic upgrade head` before import_data.py, and import_data.py stops creating the durable
     tables itself (it still drops and recreates only the seed tables).
  Tests: upgrade on an empty SQLite database; upgrade on a database that already has both tables
  with rows (rows kept); importing twice gives identical codes; build_brands_from_csv keeps codes
  after a price change and retires removed ones; My Medicines and Recently viewed v1 -> v2
  migration (Vitest); old id links redirect.
  Done 2026-11-13 (PR): 188 brands coded BR00001-BR00188 in file order (scripts/brand_codes.py, used
  by build_brands_from_csv.py). /api/alternatives/ takes a code or an old id; old id links show the
  page and switch the address bar to the code URL with history.replaceState (a server redirect
  would load the page twice, because the page streams). Brand index 43 KB (3 KB gzipped).
  Alembic runs inside import_data.py (no Render change); 0001 is a no-op on existing tables, 0002 adds
  data_reports.brand_code; local run on a database with rows: requests 24 -> 24, reports 7 -> 7.

- [x] **R1b. Targeted catalog growth (data step, after R1 is merged).**
  Same process as P7: generic records with sourced text (NHS, then the US FDA label on DailyMed,
  then the EMA product information) and how_to_take; Bangla through the review sheet, approved
  before apply; brands and Arogga prices through data/templates/brands_template.csv and
  build_brands_from_csv.py (new brands get new codes, R1); interactions re-extracted from DDInter;
  import_data.py --dry-run passes; every count in README.md and this file updated.
  Which generics, in this order: (1) those missing from the real eval prescriptions
  (data/eval: medicine lines whose generic is not in the catalog); (2) the most-written medicines
  from 1-2 doctors who try the pad (a list of names only, no patient data); (3) the top queries in
  the request log (top_requests.py). Skip herbal products, mouthwashes and combination products
  for now. Plan the list first and wait for the owner's OK.
  Coverage measure: eval_ocr.py reports, for the real handwritten prescriptions, the share of
  readable medicine lines whose medicine exists in the catalog. Baseline 2026-11-13: 21 of 34
  readable lines (62%; 36 lines including 2 nobody could read; the owner's estimate was 19 of 36).
  Target: 80% or more. results.md shows it; a unit test covers the calculation.
  Done 2026-11-13 (PR): coverage 21 -> 24 of 34 lines (70.6%, confirmed mappings only; 26 = 76.5%
  if the unconfirmed Fenomin -> Fexomin is right). The rest are combinations (AcePlus),
  herbal (Adovas), mouthwash (Benostar), antiseptic (Viodin) and Ambroxol (skipped by the owner:
  no NHS, FDA or EMA source), so 80% needs those rules to change. Added Ibn Sina (14th manufacturer,
  sourced) with 28 brands in existing groups (none on Arogga for Ibuprofen, Aspirin, Clopidogrel,
  Vildagliptin) and Chloramphenicol 0.5% eye drops (NHS, eye drops only; 11 brands, priced per
  10 ml bottle like suspensions). Now 29 generics, 227 brands (BR00189-BR00227 new), 33 compared
  groups, 55 interactions: chloramphenicol's 7 DDInter pairs are left out by the local-forms rule
  (owner, 2026-11-13: DDInter is for it by mouth or injection; we list only eye drops).
  Name mappings in the local ground truth: Mycedin -> SQ-Mycetin confirmed by the owner from the
  photo ("SQ" before, "E/E drop" after; brand alias "Mycetin" in the seed data); Fenomin ->
  Fexomin NOT confirmed (third letter n or r), so not counted as covered or matched until the box
  or a pharmacy memo confirms it. Scan matching: on a score tie the name exactly as written wins
  (Cefixime generic vs Cefixim brand). Bangla approved by the owner.
  Doctors' lists (2) and request-log queries (3) wait for doctors and PROD access.

- [x] **R2. Doctor accounts and verification.**
  Pages: /doctor (what the Rx Pad is, sign up, log in), /doctor/profile, /doctor/account,
  /doctor/privacy (public: what is stored about doctors, why, where, for how long, how to download
  and delete it; that patients' information is never stored; terms of use: the doctor is
  responsible for every prescription, MedWise BD does not choose medicines or doses). Footer link
  "For doctors" / "ডাক্তারদের জন্য".
  Stored (durable metadata, through Alembic), and nothing else:
  - doctors: email (unique, lowercased), password hash, display name (en; bn optional), degrees
    (text), specialty (text), BMDC registration number, phone to print (optional), status
    (pending | verified | rejected), rejection reason, verified_at, verified_by (owner initials),
    verify_method (text), is_demo, created_at, last_login_day.
  - chambers (max 3 per doctor): name, address, days and hours (text), phone (optional).
  - sessions: sha256 of a 32-byte random token, doctor id, created_at, last_seen, expires_at.
  - password reset tokens (hashed, 60 minutes, single use).
  Auth: email + password. Password at least 10 characters and not in a common-password list; no
  other composition rules. Hash with argon2id (argon2-cffi, pinned with every dependency) or, if
  the owner prefers no new dependency, hashlib.scrypt with OWASP parameters; decide in the plan.
  Session cookie `mw_doc`: HttpOnly, Secure (except http://localhost), SameSite=Lax, Path=/api/doctor
  (since R3, so search and other requests never carry who is asking), no
  Domain attribute; idle timeout 12 hours, absolute 7 days; "Log out" and "Log out everywhere".
  Check that Set-Cookie passes through the Next /api rewrite (Docker and a Vercel preview).
  State-changing doctor endpoints require the frontend secret header and an Origin header that
  matches the site. Login gives one error for unknown email and wrong password; after 5 failures
  for one email or 20 from one client in 15 minutes, wait 15 minutes. Sign-up: 5 per hour per
  client. No email sending: a password reset is a one-time link made by the owner with the admin
  script and sent to the doctor after confirming who they are by phone.
  Verification: new doctors are pending. backend/scripts/doctors.py, run locally with
  DATABASE_URL like top_requests.py: list, show, verify, reject, reset-link, create-demo, delete.
  `verify` prints this checklist and asks the owner to confirm each line: (1) name and
  registration number match on the official BMDC register (confirm the register's current address
  in the R2 plan); (2) identity confirmed in person, or through a chamber or hospital phone number
  the owner found independently (not the number typed at sign-up). No ID documents or photos are
  uploaded or stored. No admin web pages.
  Profile shows the status: pending; verified (badge "BMDC verified by MedWise BD" /
  "MedWise BD দ্বারা BMDC যাচাইকৃত"); rejected (with reason). Changing the BMDC number sets the
  status back to pending. Doctors can download their data (JSON) and delete their account (with
  confirm; removes profile, chambers, sessions and templates).
  Privacy note on sign-up: en "We store your email, profile and chamber details to print your
  prescriptions. We never store your patients' information." bn "প্রেসক্রিপশন ছাপাতে আমরা আপনার
  ইমেইল, প্রোফাইল ও চেম্বারের তথ্য রাখি। আপনার রোগীদের কোনো তথ্য আমরা কখনো রাখি না।"
  Tests: hashing, session idle and absolute expiry, cookie flags, lockout, Origin check, secret
  header, status changes, delete account removes every row, no password or token in logs (caplog).
  Done 2026-11-13 (PR): owner's decisions: hashlib.scrypt N=2^14 r=8 p=5, 16-byte salt, 32-byte key,
  stored as scrypt$N$r$p$salt$hash (old parameters still verify; needs_rehash at login); no doctor
  login on Vercel previews (Origin must be in SITE_ORIGINS, default the live site and
  localhost:3000; Render's CORS_ORIGINS does not list the live site, so it is not reused); data in
  Neon, AWS US East (Ohio) us-east-2 (read from the host name; not Singapore). Migration 0003 adds the
  four tables. Common passwords: SecLists (MIT), 9,159 entries of 10+ characters. Changing the name
  (not only the BMDC number) also goes back to pending, since the badge vouches for both. Reset
  links put the token after '#' (never sent to a server) and the page removes it from the address
  bar. Sign-ups and resets share one limit (5 an hour per client). The service worker never
  touches /doctor or /api/doctor; both send Cache-Control: no-store. Privacy-page facts live in
  frontend/src/lib/doctor-config.ts: contact medwisebd.team@gmail.com (no phone), Neon restore window
  1 day. The privacy page does not claim that no IP address is kept anywhere: the hosting services
  (Vercel, Render) keep standard request logs for a short time. Bangla wording fixed and approved by
  the owner (hashed, not "scrambled"; "যাচাই সফল হয়নি" for rejected).

- [x] **R3. Write and print a prescription.**
  Page /doctor/rx (login required; verified, pending and demo doctors). Sections: patient (name,
  age, sex, weight optional, date = today, editable), chief complaints, examination findings,
  diagnosis (optional), known allergies, medicines, tests, advice, follow-up date. Everything
  except medicine search is free text typed by the doctor. Every patient field: autocomplete="off",
  spellcheck={false}, translate="no", no voice input. Leaving the page with content asks to
  confirm; "New prescription" clears everything.
  Medicine lines (max 12): search with the existing search (Bangla, Banglish, English, voice).
  A suggestion shows brand, generic, strength, dosage form, manufacturer, price per unit,
  "#k of N" in its compared group with approvals x/4, and a link to the ranking page (new tab).
  The doctor may also pick a catalog generic without a brand, or write a medicine that is not in
  the catalog: "Not in MedWise yet — no price, rank or interaction check" / "MedWise-এ এখনো নেই —
  দাম, র‍্যাংক বা ইন্টারঅ্যাকশন যাচাই হয়নি".
  Per line: form word (Tab., Cap., Syp., Susp., Inj., Drop, Cream, Inhaler… from the dosage form,
  editable); dose pattern typed by the doctor (a+b+c or a+b+c+d with 0, ½, 1, 1½, 2 …, or free text
  such as "as needed"); unit (tablet, capsule, spoon, ml, drop, puff, application); food timing
  (before / after / with food / any / blank); duration (n days, weeks or months; "continue"; or
  blank); note (free text); substitution: unchecked = "Give this brand only" / "শুধু এই ব্র্যান্ড
  দিন", checked = "Same generic, strength and form allowed" / "একই জেনেরিক, শক্তি ও ধরনের অন্য
  ব্র্যান্ড দেওয়া যাবে". Shortcuts 1+0+1, 1+1+1, 0+0+1, 1+0+0, 1+1+1+1: same for every line,
  none selected.
  Under each line, the patient instruction made by a pure function from the doctor's input only,
  in en and bn. Example: 0+0+1, tablet, after food, 30 days → "রাতে ১টি, খাবারের পরে — ৩০ দিন (মোট
  ৩০টি)" / "1 at night, after food — 30 days (30 in total)". Three slots are morning, noon, night;
  four slots read "4 times a day" / "দিনে ৪ বার" with the amounts. Totals only for tablets and
  capsules with a fixed duration. Estimated cost only for catalog brands: total × price per unit,
  labelled "approx., Arogga MRP" with the price date.
  Warnings panel, information for the doctor and never blocking: DDInter interactions among
  catalog generics (existing interaction API, major first, DDInter credit; the call sends only
  generic ids); the same generic twice; lines not in the catalog ("not checked").
  Print: "Print / Save as PDF" opens an A4 print layout made with HTML and print CSS; the browser's
  print gives the PDF and shapes Bangla correctly (no PDF library). Letterhead from the profile:
  name, degrees, specialty, BMDC number, the chamber the doctor picks with days and hours, phone.
  Patient line. Left column: complaints, findings, diagnosis, allergies, tests. Right column: Rx
  lines (brand, generic in brackets, strength), pattern, food, duration, the patient instruction
  in Bangla, English or both (doctor's choice), substitution note per line; then advice and
  follow-up; a signature line for signing by hand. Footer: "Made with MedWise BD. MedWise BD does
  not choose medicines or doses." / "MedWise BD দিয়ে তৈরি। MedWise BD ওষুধ বা ডোজ বেছে দেয় না।"
  plus the demo or not-verified watermark. Long prescriptions continue on a second page with the
  doctor's name and page number. Print is always light.
  Tests (Vitest): instruction sentences in en and bn (halves, 4-slot patterns, free text, missing
  parts, Bangla digits), totals, cost, duplicate generic. Browser: fill a whole prescription with
  a unique patient name, then check no request URL, body or header and no storage holds it, and
  that every patient field has autocomplete off, spellcheck off and translate="no"; print layout
  in en and bn on A4.
  Done 2026-11-13 (PR): owner's choices: patient instructions print in Bangla and English by default
  (the doctor can switch), approx. cost on screen only, the existing server search. Search requests
  carry only the typed text: the session cookie moved to Path=/api/doctor (R2's Path=/ cookie is
  cleared at login and logout); the pad waits 250 ms after typing, needs 2 characters, caches
  answers, cancels stale requests and sends at most 60 searches a minute per tab (server: 120 per
  client), retrying by itself after a 429 (e.g. many users behind one hospital Wi-Fi). Logic in
  lib/rx.ts and lib/rx-search.ts (Vitest). Print: named @page "rx" (A4); the doctor's name on page
  2 onwards, the footer and "page / pages" sit in the page margins (text from CSS custom properties
  set by the pad); the DEMO or not-verified mark is a banner on page 1 plus a fixed diagonal mark
  on every page; the site header and footer are hidden in print. Rejected doctors cannot use the pad.
  Browser test (33 checks): no request, storage area or cookie holds the patient's details; Bangla
  in the PDF is checked on the print view (PDF text extraction cannot rebuild Bangla conjuncts).

- [ ] **R4. QR, signature and the patient page.**
  "Finalize" builds, in the browser, a versioned compact payload of the medicine lines only (brand
  code, or generic name + strength + form, or free-text name of at most 40 characters; pattern,
  unit, food, duration, substitution flag) and the issue date. No patient fields, complaints,
  findings, diagnosis, allergies, tests or advice. The browser computes SHA-256 of the canonical
  payload (WebCrypto) and sends only that hash to POST /api/doctor/rx/sign (logged-in doctor,
  300 a day per doctor). The server returns {doctor_id, issued_at, sig}, where
  sig = HMAC-SHA256(RX_SIGNING_SECRET, version|doctor_id|issued_at|hash). The server never sees
  the medicines and stores nothing about the prescription. RX_SIGNING_SECRET lives only in
  backend/.env and on Render.
  The printed QR is https://<site>/rx#<base64url payload with doctor_id, issued_at and sig>. The
  part after # never reaches any server. A 12-line prescription must give a QR that a mid-range
  Android phone scans from a printed A4; measure in the plan at 4 cm and 5 cm, show payload and QR
  sizes, and use CompressionStream ("deflate-raw") if needed. Editing after Finalize needs a new
  Finalize. Printed next to the QR: "Scan to see these medicines in MedWise BD" /
  "MedWise BD-তে এই ওষুধগুলো দেখতে স্ক্যান করুন".
  Page /rx (public, no login) decodes on the device and loads GET /api/brands/index once (cached
  like other GET data), looking codes up on the device, so nothing about the prescription reaches
  the server. Verification sends only {doctor_id, issued_at, hash, sig} to POST /api/rx/verify
  (rate-limited), which answers valid or not and, when valid, the doctor's public details (name,
  degrees, BMDC number, status, demo). Wording (the QR proves who issued it, not that the medicines
  are right, and it can be copied):
  valid: "Issued by Dr. X on <date>. MedWise BD checked the doctor's signature on this QR, not the
  medicines or doses." / "ডা. X, <date>-এ দিয়েছেন। MedWise BD এই QR-এ ডাক্তারের স্বাক্ষর যাচাই
  করেছে, ওষুধ বা ডোজ নয়।";
  always, for pharmacists: "A QR can be copied. Before giving medicines, check the doctor's
  signature on the paper." / "QR কপি করা যায়। ওষুধ দেওয়ার আগে কাগজে ডাক্তারের সই দেখুন।";
  not valid: "Could not check this QR. The paper prescription is what counts." / "এই QR যাচাই করা
  যায়নি। কাগজের প্রেসক্রিপশনটিই আসল।". Offline: show the medicines and say checking needs internet.
  Each line: name as written, generic, strength and form, the instruction (language toggle),
  total, approx. cost for catalog brands, a "How to take" link to the generic page (P4), and the
  substitution note. Only when substitution is allowed: a link "Other brands of the same generic
  (ranked)" to the existing alternatives page. Never the word "switch". No interaction warnings on
  /rx (the doctor saw them while writing). Buttons: "Save to My Medicines" (P8 module, by brand
  code; units per day from the doctor's pattern; reminder times typed by the user as in P8), "Find
  pharmacies" (P9), and for the follow-up date "Add to calendar" (.ics made on the device, title
  "Follow-up visit" / "ফলো-আপ ভিজিট", option to hide the doctor's name). Always show the existing
  "consult your doctor or pharmacist" disclaimer.
  If RX_SIGNING_SECRET changes, old QR codes still open but show "Could not check". Document it.
  Tests: payload round trip and fuzz (bad input never crashes the page), HMAC sign and verify,
  tampered payload fails, demo and unverified states. Browser: open /rx from a generated URL and
  check that no request carries a medicine name.

- [ ] **R5. Templates and favourite tests.**
  Doctors save the current medicine lines, plus tests and advice text, as a named template; list,
  rename, edit, delete; "Apply" adds the lines to the current prescription. No patient fields are
  ever saved in a template; the save box warns: "Do not write patient information here." /
  "এখানে রোগীর তথ্য লিখবেন না।" Max 100 templates per doctor, 12 lines each. Stored per doctor
  through Alembic, by brand code with a name snapshot; a brand that left the catalog becomes a
  free-text line with a note. Private to the doctor: not shared, listed, ranked or aggregated.
  Favourite tests: the doctor's own list of test names (max 50) shown as chips in the tests box.
  Not in catalog: on Finalize, each free-text medicine name (name only, max 80 characters) goes to
  the existing request log with source "rx-pad" (no doctor id, no patient data), so the team
  learns what to add. The pad says so under the search box.
  Tests: CRUD, ownership (doctor A gets 404 for doctor B's templates), limits, catalog change,
  request log rows carry only name, source and day.

- [ ] **R6 (optional). Chamber serial board, on this computer only.**
  /doctor/queue, no login needed: serial numbers only, no names or any other patient detail
  (keeps the rule that patient information is never stored). Add the next number; statuses waiting
  / with the doctor / done / no-show; "Call next"; a full-screen view for a TV. Kept only in this
  browser (localStorage, versioned module, try/catch), cleared automatically at midnight and by
  "Clear today". Nothing is sent to our backend. The page says "Saved only on this computer,
  cleared every night." / "শুধু এই কম্পিউটারে, প্রতি রাতে মুছে যায়।" Vitest for the queue logic;
  browser test that no request carries queue data and that the page has no field for a name.

Not doing in Phase 5 (by design): telemedicine or video calls, patient records or report storage,
online appointment booking, payments or earnings, AI summaries of reports, AI-suggested medicines,
doses or tests, uploading ID documents.
