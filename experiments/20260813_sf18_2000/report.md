# NSCE vs Stockfish 18 Elo 2000 (N=40)

Date: 2026-08-13.

- NSCE: `build/nsce`, `tools/configs/baseline.uci` (`EvalFile=internal`; KAT and controller SPRTs did not accept H1)
- Opponent: Stockfish 18 AVX2, `UCI_LimitStrength=true`, `UCI_Elo=2000`
- Games: **40** (paired colors, `openings_balanced.epd`, seed 20260813)
- Movetime: 100 ms, Hash 16, Threads 1, max plies 120
- Status oracle: **NSCE `status`** (never Stockfish)

| Rung | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| SF18 Elo 2000 | 11-13-16 | 0.438 | −44 ± 90 |

N=20 on the same protocol was 7-8-5 (0.550, +35 ± 120). The ±95% interval at N=40 still includes zero. Equal-compute unrestricted Stockfish is not this KPI.

See `elo_ladder.json` and `manifest.json`.
