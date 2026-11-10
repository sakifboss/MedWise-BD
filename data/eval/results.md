# OCR evaluation results

Run on 2026-11-10 with `backend/scripts/eval_ocr.py`. 23 images.
Models that answered: gemini-3.5-flash-lite (22), gemini-3.5-flash (1).
The app's first-choice model (gemini-3.8-flash) did not answer (busy), so its fallback models did, as they would for a user at that moment.
Images are resized like the app (longest side 2000 px, JPEG quality 85).

## How it is scored

- **Reading**: a medicine read from the image is correct when its name matches the ground truth
  (rapidfuzz ratio >= 85, ignoring case, spaces, dots, hyphens and dosage-form words
  such as "tab" or "mouthwash") and, when both have a strength, the strengths agree (a bare
  number like "500" agrees with "500 mg").
  Recall = correct / medicines on the prescriptions; precision = correct / medicines read.
  Duplicates read from one image are counted once. A read of a line nobody could read (see
  "Not scored" below) does not count against precision.
- **Matching**: of the medicines on the prescriptions that exist in our catalog, how many the app
  pre-selected with the right generic and strength ("Matched"), and how many it at least listed
  among the options the user picks from ("Offered").

## Totals

| Subset | Images | On prescriptions | Read | Correct | Recall | Precision | Matched | Match rate | Offered | Offered rate |
|---|---|---|---|---|---|---|---|---|---|---|
| real_handwritten | 10 | 34 | 34 | 28 | 82.4% | 82.4% | 11/15 | 73.3% | 12/15 | 80.0% |
| synthetic_printed | 10 | 13 | 13 | 13 | 100.0% | 100.0% | 0/0 | n/a | 0/0 | n/a |
| degraded_copies | 3 | 9 | 9 | 8 | 88.9% | 88.9% | 4/4 | 100.0% | 4/4 | 100.0% |
| overall | 23 | 56 | 56 | 49 | 87.5% | 87.5% | 15/19 | 78.9% | 16/19 | 84.2% |

## The images

- **real_handwritten**: real handwritten prescriptions (scanned with CamScanner).
- **synthetic_printed**: computer-generated printed prescriptions with fictional medicine names (shows the pipeline works; not real-world accuracy; no catalog matches possible).
- **degraded_copies**: blurred / dimmed and rotated / low-resolution copies of real images.
- Not scored: Kexam on rx07 and rx08: the team could not read the name, so it is not scored.
- Ground truth was written by the team from the images; names they could not read are left out.
- This file holds only file ids and medicine names, no patient or doctor details.

## Per image

| Image | Subset | Correct | Missed | Extra (read, not on the prescription) | Matched |
|---|---|---|---|---|---|
| rx01 | real_handwritten | 2/4 | AcePlus, Montene | Ace Plm, Monters | 0/1 |
| rx02 | real_handwritten | 3/3 | - | - | 2/2 |
| rx03 | real_handwritten | 3/4 | Fenomin | Feronion | 1/1 |
| rx04 | real_handwritten | 3/3 | - | - | 2/2 |
| rx05 | real_handwritten | 4/5 | Zithrin | Zithrox | 1/2 |
| rx06 | real_handwritten | 3/3 | - | - | 1/1 |
| rx07 | real_handwritten | 5/5 | - | - | 1/2 |
| rx08 | real_handwritten | 1/3 | Montene, Romycin | Montek, Ponysan | 1/2 |
| rx09 | real_handwritten | 3/3 | - | - | 1/1 |
| rx10 | real_handwritten | 1/1 | - | - | 1/1 |
| rx11 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx12 | synthetic_printed | 2/2 | - | - | 0/0 |
| rx13 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx14 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx15 | synthetic_printed | 2/2 | - | - | 0/0 |
| rx16 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx17 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx18 | synthetic_printed | 2/2 | - | - | 0/0 |
| rx19 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx20 | synthetic_printed | 1/1 | - | - | 0/0 |
| rx21 | degraded_copies | 3/3 | - | - | 2/2 |
| rx22 | degraded_copies | 3/3 | - | - | 1/1 |
| rx23 | degraded_copies | 2/3 | Viodin | Viadin M/W | 1/1 |
