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
      api/        # routers: search, generics, alternatives, manufacturers, interactions, prescription
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
names a disease or a medicine.

## Security hardening (approved 2026-11-04)
Same workflow as the roadmap: one step at a time; tests, ruff, lint, typecheck, build; for anything
that touches the frontend, rerun the browser test suites (a too-strict CSP breaks pages silently);
commit + push -> verify live -> tick the box -> stop for the user's review.

Already in place: HTTPS + HSTS (Vercel), CORS closed to other origins, uploads checked by file
bytes and size and never stored, OCR rate limits (per client + global daily cap), no secrets in
git history, non-root Docker images, Next.js patched to 16.4.2.

- [x] **S1. Security headers.** Frontend: nonce-based Content-Security-Policy set per request in
  `frontend/src/proxy.ts`, plus frame-ancestors/X-Frame-Options, nosniff, Referrer-Policy,
  Permissions-Policy (microphone for voice search only), no X-Powered-By. Backend: nosniff,
  frame denial and a locked-down CSP on API responses (not on /docs).
- [x] **S2. Only our frontend may call the prescription endpoint.** The Next proxy adds a secret
  header (`FRONTEND_SHARED_SECRET`, set on Vercel and Render) to /api/prescription; the backend
  rejects OCR requests without it, so nobody can drain the Gemini quota by calling Render directly.
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

- [ ] **P1. Price score = min_price / price.**
  In backend/app/services/ranking.py replace the min-max price score with
  P = min_price / price (1.0 for the cheapest brand, and 1.0 when all prices are equal).
  Update the module docstring, the formula in this file, and test_ranking.py (price_score cases and
  the hand-worked A/B/C example). Real-data check after import, Omeprazole 20 mg capsule:
  Losectil 88.5, Seclo 87.5, Proceptin 83.2 (Seclo moves from 3rd to 2nd). In Esomeprazole 20 mg
  the top pick changes from Maxpro to Nexum MUPS; this is expected (quality first).

- [ ] **P2. Same-price banner.**
  When every brand in a compared group (same generic, strength and dosage form) has the same price
  per unit, the ranking page and the alternatives page show one banner above the list:
  en "All these brands cost the same (Tk X per unit). The top-ranked one costs nothing extra."
  bn "এই সবগুলো ব্র্যান্ডের দাম একই (প্রতি ইউনিট ৳X)। তালিকার প্রথমটি নিতে কোনো বাড়তি খরচ নেই।"
  Use the app's existing price/number formatting. Hide it when the group has only one brand.
  Prefer computing it from data the page already has; add an API field only if needed.
  Today 7 of 25 groups qualify (e.g. Paracetamol 500 mg, Losartan 50 mg, Cetirizine 10 mg).
  Tests: unit test for the all-equal check; check one equal-price and one mixed-price page.

- [ ] **P3. OCR accuracy evaluation.**
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

- [ ] **P4. "How to take" from the label.**
  Add optional how_to_take (list of short lines) and how_to_take_bn per record in generics.json,
  through schema, model, import, API and the generic page (section "How to take" /
  "কীভাবে খাবেন", with the source link under it). Content: only what the generic's existing
  source_urls (NHS page or FDA label) say about timing with meals, milk/dairy, alcohol, or other
  things to take apart from it. Keep the source's wording. If the source says nothing, leave the
  field empty and hide the section. Never write our own advice, doses or durations.
  Draft English for all generics by reading the cited pages. Bangla goes through the existing
  review sheet: extend build_generics_bn.py so export/apply include the new field; the team
  approves every line before apply.

- [ ] **P5. "Request this medicine".**
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

- [ ] **P6. Offline mode for saved pages.**
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

- [ ] **P7. Eight more generics (data step).**
  Add: Fexofenadine, Ketotifen, Domperidone, Famotidine, Levocetirizine, Rosuvastatin, Bisoprolol,
  Vildagliptin. For each, use the strength and dosage form with the most brands on Arogga.
  Warfarin 5 mg has only one brand: add brands, or drop the group if no second brand is found.
  1. Generic records: same rules as roadmap step 0 (sourced text, source_urls, keep the source's
     wording). Sources in order: NHS medicine page, then the US FDA label on DailyMed, then the EMA
     product information (e.g. vildagliptin has no FDA label). Fill how_to_take as in P4.
  2. Bangla: through the review sheet; the team approves before apply.
  3. Brands and prices: add the new groups to data/templates/brands_template.csv for the team to
     fill (Arogga MRP + page link, only the 13 manufacturers in manufacturers.json), then run
     build_brands_from_csv.py and fix any reported rows.
  4. Interactions: re-run extract_ddinter.py with the DDInter CSVs in data/raw/ddinter/; extend
     DDINTER_ALIASES if DDInter spells a name differently; report generics it could not find.
  5. import_data.py --dry-run must pass. Update every count in README.md and this file.

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

- [ ] **P8. My Medicines (on this device only).**
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

- [ ] **P9. Sylhet pharmacy finder (real locations, no stock claims).**
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

- [ ] **P10. Symptom guide (no diagnosis, no medicines).**
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
