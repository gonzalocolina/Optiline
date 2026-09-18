# Promoted NSCE vs Stockfish 18 Elo 2200 (N=200)

Date: 2026-09-09 (report 2026-09-15). Follow-up to N=40 and N=80
([N=40](../20260903_sf18_2200_rw0/report.md),
[N=80](../20260904_sf18_2200_rw0_n80/report.md)). Same protocol, same seed
20260814 (200-game schedule extends the earlier pair list). `baseline.uci`
unchanged.

- NSCE: `build/nsce`, `tools/configs/baseline.uci`
  (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`, Hash 16, Threads 1,
  extras on, policy/controller off)
- Opponent: pinned `third_party/stockfish/stockfish-18` (`6b087694…`),
  `UCI_LimitStrength=true`, `UCI_Elo=2200`, Hash 16, Threads 1
- Games: **200**, 100 ms, max plies 120, `openings_balanced.epd`, paired colors
- Status oracle: **NSCE `status`**
- Log: 200 finished games, **67-88-45** (matches `elo_ladder.json`)

| Rung | N | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: | ---: |
| SF18 Elo 2000 | 40 | 25-8-7 | 0.725 | +168 ± 114 |
| SF18 Elo 2200 | 40 | 17-14-9 | 0.600 | +70 ± 90 |
| SF18 Elo 2200 | 80 | 30-25-25 | 0.531 | +22 ± 64 |
| **SF18 Elo 2200** | **200** | **67-88-45** | **0.555** | **+38 ± 36** |

N=40 and N=80 intervals include 0. N=200 lower bound is **+2** (excludes 0).
That is the claim-quality sample for this limited-strength rung. `UCI_Elo` is
not a precise rating. Unrestricted equal-compute Stockfish 18 is still
unplayed.
