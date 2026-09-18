# Promoted NSCE vs Stockfish 18 Elo 2000 (N=40)

Date: 2026-09-03.

- NSCE: `build/nsce`, `tools/configs/baseline.uci`
  (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`, extras on; eval SPRT H1)
- Opponent: pinned `third_party/stockfish/stockfish-18` (`6b087694…`),
  `UCI_LimitStrength=true`, `UCI_Elo=2000`
- Games: **40** (paired colors, `openings_balanced.epd`, seed 20260814)
- Movetime: 100 ms, Hash 16, Threads 1, max plies 120
- Status oracle: **NSCE `status`**

| Rung | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| SF18 Elo 2000 | **25-8-7** | **0.725** | **+168 ± 114** |

Interval excludes 0. Previous internal-eval rung was 11-13-16, −44 ± 90
([sf18_2000](../20260813_sf18_2000/report.md)). This promoted net **wins**
the 2000 KPI. Next: SF18 Elo 2200, N≥40, same protocol. Unrestricted
equal-compute Stockfish is still unplayed.
