# NSCE vs Stockfish 18 Elo 2200 (N=40)

Date: 2026-08-13.

- NSCE: `build/nsce`, `tools/configs/baseline.uci` (`EvalFile=internal`)
- Opponent: Stockfish 18 AVX2, `UCI_LimitStrength=true`, `UCI_Elo=2200`
- Games: **40** (paired colors, `openings_balanced.epd`, seed 20260813)
- Movetime: 100 ms, Hash 16, Threads 1, max plies 120
- Status oracle: **NSCE `status`** (never Stockfish)

| Rung | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| SF18 Elo 2200 | 10-17-13 | 0.463 | −26 ± 82 |

Interval includes zero. `UCI_Elo` is not a precise rating; 2200 is not necessarily
stronger than the 2000 sample. Unrestricted equal-compute Stockfish was not played.

See `elo_ladder.json` and `manifest.json`.
