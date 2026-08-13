# Time-management soft-stop (SPRT)

Date: 2026-08-13. Candidate: do not start another iterative-deepening
iteration if remaining time `< last_iter` (was `< last_iter / 2`). Same
`baseline.uci` on both sides. Binary A: extras-flag engine without the TM
change (`/tmp/nsce_pre_tm`). Binary B: same tree with only that one-liner.

Hypothesis: 2× timed nodes is about one extra ID iteration; skip starting a
depth you cannot finish.

## SPRT

- `--engine /tmp/nsce_pre_tm --engine-b build/nsce`, both `baseline.uci`
- 100 ms, min 40 / max 200, seed 20260813, `openings_balanced.epd`

| Decision | W-D-L (soft-stop) | Games | LLR |
| --- | ---: | ---: | ---: |
| **inconclusive** | 20-161-19 | 200 | +0.09 |

Score 0.503. Coin flip at ±5 Elo. **Not promoted.** The one-liner was reverted
so the frozen search matches the measured Hash/extras baseline. Fail-low extra
budget was not part of this candidate.
