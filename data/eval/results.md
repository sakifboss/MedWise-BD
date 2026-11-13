# OCR evaluation results

Run on 2026-11-13 with `backend/scripts/eval_ocr.py`. 23 images.
Models that answered: gpt-6.1-terra (23).

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
| real_handwritten | 10 | 34 | 34 | 32 | 94.1% | 94.1% | 20/24 | 83.3% | 22/24 | 91.7% |
| synthetic_printed | 10 | 13 | 0 | 0 | 0.0% | n/a | 0/0 | n/a | 0/0 | n/a |
| degraded_copies | 3 | 9 | 9 | 9 | 100.0% | 100.0% | 7/7 | 100.0% | 7/7 | 100.0% |
| overall | 23 | 56 | 43 | 41 | 73.2% | 95.3% | 27/31 | 87.1% | 29/31 | 93.5% |

## Catalog coverage

Of the readable medicine lines, how many name a medicine that is in our catalog (its brand name,
its generic name, or the generic the team wrote in the ground truth when the written name differs
from the pack). Lines nobody could read are left out. Target for the real handwritten
prescriptions: 80% or more. "Coverage" counts confirmed mappings only (the main number); the next
column also counts mappings the team has not confirmed yet.

| Subset | Lines in catalog | Coverage | With unconfirmed mappings | Unconfirmed | Not in catalog |
|---|---|---|---|---|---|
| real_handwritten | 24 of 34 | 70.6% | 76.5% | Fenomin (2) | AcePlus (3), Adovas, Ambrox (2), Benostar, Viodin |
| synthetic_printed | 0 of 13 | 0.0% | 0.0% | - | DemoCream-1, DemoDrop-1, DemoMed-A, DemoMed-B, DemoMed-C, DemoMed-D, DemoMed-E, DemoMed-F, DemoMed-G, DemoMed-H, DemoMed-I, DemoMed-J, DemoMed-K |
| degraded_copies | 7 of 9 | 77.8% | 77.8% | - | Ambrox, Viodin |
| overall | 31 of 56 | 55.4% | 58.9% | Fenomin (2) | AcePlus (3), Adovas, Ambrox (3), Benostar, DemoCream-1, DemoDrop-1, DemoMed-A, DemoMed-B, DemoMed-C, DemoMed-D, DemoMed-E, DemoMed-F, DemoMed-G, DemoMed-H, DemoMed-I, DemoMed-J, DemoMed-K, Viodin (2) |

Names written differently from the pack, as mapped by the team:

- Fenomin -> Fexomin (Fexofenadine), NOT confirmed (not counted as covered or matched): the third letter looks like n or r, not x; confirm from the medicine box or pharmacy memo.
- Mycedin -> SQ-Mycetin (Chloramphenicol), confirmed: the photo shows 'SQ' before the name and 'E/E drop' after it (owner, 2026-11-13).

## The images

- **real_handwritten**: real handwritten prescriptions (scanned with CamScanner).
- **synthetic_printed**: computer-generated printed prescriptions with fictional medicine names (shows the pipeline works; not real-world accuracy; no catalog matches possible). Each page says "NOT A REAL PRESCRIPTION"; a model that follows our instruction to return nothing for a non-prescription scores 0 here, which is the intended behaviour.
- **degraded_copies**: blurred / dimmed and rotated / low-resolution copies of real images.
- Not scored: Kexam on rx07 and rx08: the team could not read the name, so it is not scored.
- Ground truth was written by the team from the images; names they could not read are left out.
- This file holds only file ids and medicine names, no patient or doctor details.

## Per image

| Image | Subset | Correct | Missed | Extra (read, not on the prescription) | Matched |
|---|---|---|---|---|---|
| rx01 | real_handwritten | 3/4 | Montene | Montex | 0/1 |
| rx02 | real_handwritten | 3/3 | - | - | 3/3 |
| rx03 | real_handwritten | 4/4 | - | - | 1/1 |
| rx04 | real_handwritten | 3/3 | - | - | 2/3 |
| rx05 | real_handwritten | 5/5 | - | - | 4/4 |
| rx06 | real_handwritten | 3/3 | - | - | 2/2 |
| rx07 | real_handwritten | 5/5 | - | - | 3/4 |
| rx08 | real_handwritten | 2/3 | Montene | Montex | 2/3 |
| rx09 | real_handwritten | 3/3 | - | - | 2/2 |
| rx10 | real_handwritten | 1/1 | - | - | 1/1 |
| rx11 | synthetic_printed | 0/1 | DemoMed-A | - | 0/0 |
| rx12 | synthetic_printed | 0/2 | DemoMed-B, DemoMed-C | - | 0/0 |
| rx13 | synthetic_printed | 0/1 | DemoCream-1 | - | 0/0 |
| rx14 | synthetic_printed | 0/1 | DemoMed-D | - | 0/0 |
| rx15 | synthetic_printed | 0/2 | DemoMed-E, DemoMed-F | - | 0/0 |
| rx16 | synthetic_printed | 0/1 | DemoMed-G | - | 0/0 |
| rx17 | synthetic_printed | 0/1 | DemoMed-H | - | 0/0 |
| rx18 | synthetic_printed | 0/2 | DemoMed-I, DemoMed-J | - | 0/0 |
| rx19 | synthetic_printed | 0/1 | DemoMed-K | - | 0/0 |
| rx20 | synthetic_printed | 0/1 | DemoDrop-1 | - | 0/0 |
| rx21 | degraded_copies | 3/3 | - | - | 3/3 |
| rx22 | degraded_copies | 3/3 | - | - | 2/2 |
| rx23 | degraded_copies | 3/3 | - | - | 2/2 |
