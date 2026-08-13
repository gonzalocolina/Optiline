# SF18 limited-strength ladder (N≥40)

Date: 2026-08-13. Frozen NSCE baseline after the KAT and controller SPRT gates
(neither accepted H1, so `EvalFile=internal` and `UseSearchController=false`).

- NSCE: `build/nsce`, `tools/configs/baseline.uci`, Hash 16, Threads 1
- Opponent: Stockfish 18 AVX2 (`/tmp/sf18extract/stockfish/stockfish-ubuntu-x86-64-avx2`)
- `UCI_LimitStrength=true`, movetime 100 ms, max plies 120
- Openings: `tools/openings_balanced.epd`, seed 20260813
- Status oracle: NSCE `status` only

| Rung | N | W-D-L (NSCE) | Score | Elo ±95% | Details |
| --- | ---: | ---: | ---: | ---: | --- |
| SF18 Elo 2000 | 40 | 11-13-16 | 0.438 | −44 ± 90 | [20260813_sf18_2000](../20260813_sf18_2000/report.md) |
| SF18 Elo 2200 | 40 | 10-17-13 | 0.463 | −26 ± 82 | [20260813_sf18_2200](../20260813_sf18_2200/report.md) |

Both intervals include equality. N=20 at 2000 had been 7-8-5 (+35 ± 120); the
larger sample is the one that counts for promotion.

**Not played:** equal-compute Stockfish without `UCI_LimitStrength`. That remains
the north star, not this week’s KPI.
