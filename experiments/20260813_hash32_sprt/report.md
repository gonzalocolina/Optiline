# Hash 32 vs Hash 16 (SPRT)

Date: 2026-08-13. Same binary, `EvalFile=internal`, extras on. Candidate only
changes `Hash` from 16 MB to 32 MB. Hypothesis: 2× timed nodes fill a 16 MB TT
faster, so extra hash could buy Elo at 100 ms.

## SPRT

- `hash32.uci` vs `baseline.uci`, 100 ms, min 40 / max 200, seed 20260813
- Openings: `openings_balanced.epd`

| Decision | W-D-L (Hash 32) | Games | LLR |
| --- | ---: | ---: | ---: |
| **inconclusive** | 19-168-13 | 200 | +0.54 |

Score 0.515. Slightly positive, not enough for H1 at ±5 Elo. Keep **Hash 16** on
the frozen baseline. Do not mix Hash 32 into another candidate.
