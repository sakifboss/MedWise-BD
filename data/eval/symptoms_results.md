# Symptom guide evaluation

Date: 2026-11-10 · Cases: 40 (invented, no real patients; `data/eval/symptoms.json`) · Models: gemini-3.5-flash-lite (32), gemini-3.6-flash (6), gemini-3.5-flash (2)

The whole pipeline ran: Gemini, then the strict schema, the medicine/dose/diagnosis
checks and the fixed rules (child -> paediatrics, pregnant -> obstetrics).

| | Red-flag recall | False alarms | Specialty accuracy |
|---|---|---|---|
| **All** | 13/13 (100.0%) | 0/27 | 27/27 (100.0%) |
| en | 5/5 (100.0%) | 0/9 | 9/9 (100.0%) |
| bn | 4/4 (100.0%) | 0/10 | 10/10 (100.0%) |
| banglish | 4/4 (100.0%) | 0/8 | 8/8 (100.0%) |

Red-flag recall must be 100%: every emergency case showed the emergency screen.

Doctor notes on the ordinary cases: ok 27 (`ok` = the AI note was used; anything else = the note was built from the answers).

## Misses

None.
