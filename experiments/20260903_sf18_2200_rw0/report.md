# Promoted NSCE vs Stockfish 18 Elo 2200 (N=40)

Date: 2026-09-03. After winning the 2000 rung
([sf18 2000 rw0](../20260903_sf18_2000_rw0/report.md)).

- NSCE: `build/nsce`, `tools/configs/baseline.uci`
  (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`)
- Opponent: pinned `third_party/stockfish/stockfish-18` (`6b087694…`),
  `UCI_LimitStrength=true`, `UCI_Elo=2200`
- Games: **40** (paired colors, `openings_balanced.epd`, seed 20260814)
- Movetime: 100 ms, Hash 16, Threads 1, max plies 120
- Status oracle: **NSCE `status`**

| Rung | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| SF18 Elo 2200 | **17-14-9** | **0.600** | **+70 ± 90** |

Point estimate is above the limited-2200 opponent. The interval includes 0.
Previous internal-eval 2200 was 10-17-13, −26 ± 82
([sf18_ladder](../20260813_sf18_ladder/report.md)). `UCI_Elo` is not a precise
rating. Unrestricted equal-compute Stockfish is still unplayed.
