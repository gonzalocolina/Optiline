# Promoted NSCE vs Stockfish 18 Elo 2200 (N=80)

Date: 2026-09-04. Follow-up to N=40
([sf18 2200 N=40](../20260903_sf18_2200_rw0/report.md)), same protocol,
same seed 20260814 (80-game schedule extends the 40-game pair list).

- NSCE: `build/nsce`, `tools/configs/baseline.uci`
  (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`)
- Opponent: pinned `third_party/stockfish/stockfish-18` (`6b087694…`),
  `UCI_LimitStrength=true`, `UCI_Elo=2200`
- Games: **80**, 100 ms, Hash 16, Threads 1, max plies 120
- Status oracle: **NSCE `status`**

| Rung | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| SF18 Elo 2200 N=40 | 17-14-9 | 0.600 | +70 ± 90 |
| **SF18 Elo 2200 N=80** | **30-25-25** | **0.531** | **+22 ± 64** |

Interval includes 0. The N=40 plus did not hold (same pattern as Elo 2000
N=20 vs N=40). Do not treat this as ≥2200. Unrestricted SF is still unplayed.
