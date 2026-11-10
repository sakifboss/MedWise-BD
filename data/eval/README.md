# Evaluations

Two evaluations live here: prescription reading (below) and the symptom guide
(`symptoms.json`, invented cases only; run `cd backend && python scripts/eval_symptoms.py`, results
in `symptoms_results.md`; see the main README, "Symptom guide").

# OCR evaluation

Measures how well MedWise BD reads prescription photos (Gemini) and matches the medicines to our
catalog, using the app's own code. The latest numbers are in [results.md](results.md).

## Privacy

Real prescriptions hold personal data, so `prescriptions/` and `cache/` are **gitignored**. Only
this README, `subsets.json` (image ids) and `results.md` (image ids and medicine names) are
committed. Before adding a photo:

- get the owner's permission, and tell them the photo is sent to Google's Gemini service;
- cover or blur the patient's name, age and phone number, and the doctor's name. Reading only needs
  the medicine lines.

Run `git status` before every commit: no image or `rxNN.json` may appear.

## Adding images

1. Put the photo in `prescriptions/` as `rxNN.jpg` (or `.png` / `.webp`).
2. Next to it, write `rxNN.json` with what a careful person reads on the prescription:

   ```json
   {"medicines": [{"name": "Seclo", "strength": "20 mg"}, {"name": "Napa", "strength": null}]}
   ```

   - `name`: as written. `strength`: as written, or `null` when none is written.
   - Every medicine on the page, each once. Leave out crossed-out lines and names nobody can read:
     add `"unreadable": N` (how many such lines) so the model's reads of them are not counted as
     wrong, and explain them under `excluded` in `subsets.json`.
   - Numbers in a circle (how many tablets) are not strengths.
   - When the written name differs from the catalog's brand name, add the generic:
     `{"name": "Nexum", "strength": "20 mg", "generic": "Esomeprazole"}` (catalog: "Nexum MUPS").
3. Add the id to a subset in `subsets.json` (`real_handwritten`, `synthetic_printed`,
   `degraded_copies`). Results are reported per subset and overall.

## Running

From `backend/`, with `GEMINI_API_KEY` in `backend/.env`:

```bash
python scripts/eval_ocr.py                    # read new images, score all, write results.md
python scripts/eval_ocr.py --only rx01,rx02   # some images only
python scripts/eval_ocr.py --refresh          # ask Gemini again even when cached
python scripts/eval_ocr.py --threshold 90     # stricter name match (default 85)
python scripts/eval_ocr.py --no-write         # print only
# One model only (no fallbacks), cached in cache/<model>/, so runs can resume the next day:
python scripts/eval_ocr.py --model gemini-3.8-flash --out ../data/eval/results_gemini-3.8-flash.md
```

- Each photo is resized exactly like the app does before upload (longest side 2000 px, JPEG 0.85).
- Gemini's answer is cached in `cache/rxNN.json` (keyed by the photo's hash), so changing the ground
  truth and re-running costs no Gemini calls. A new or edited photo is read again.
- Calls are spaced (`--delay`, default 6 s) to stay inside the free tier. When Gemini is busy
  (429/503) the image is tried again after `--retry-wait` seconds (default 65), up to `--retries`
  times (default 3); after that it is reported as an error and read on the next run.
- Free-tier limits are per Google Cloud project and per model; some models allow only 20 requests a
  day. Use a key from a separate project for evaluation, so a run never uses up the live app's
  quota. With `--model`, finished images stay cached, so a long run can continue the next day.
- Matching runs the app's `match_prescription` on a temporary SQLite database loaded from
  `data/seed`. It never touches the production database.

## How it is scored

- **Reading**: a medicine read from the photo is correct when its name matches the ground truth
  (rapidfuzz ratio >= 85, ignoring case, spaces, dots, hyphens and dosage-form words such as
  "tab", "syp" or "mouthwash") and, when both sides have a strength, they agree. A bare number
  ("Romycin 500") agrees with "500 mg". Recall = correct / medicines on the prescriptions;
  precision = correct / medicines read. Duplicates read from one image count once. Pairs that pass the threshold without being identical are printed as
  "close name" so they can be checked by eye (e.g. "DemoMed-A" vs "DemoMed-B" scores 87.5).
- **Matching**: of the medicines on the prescriptions that exist in our catalog, how many the app
  pre-selected with the right generic and strength ("Matched"), and how many it at least listed
  among the options the user picks from ("Offered").
