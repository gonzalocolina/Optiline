# fastchess match — 20260915_search_leaves40k_full

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci`
- B: `leaves40k` = `build/nsce` + `tools/configs/nnue_search_leaves40k.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs leaves40k (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 116.52 +/- 24.98, nElo: 139.96 +/- 27.80
LOS: 100.00 %, DrawRatio: 31.33 %, PairsRatio: 3.79
Games: 600, Wins: 335, Losses: 141, Draws: 124, Points: 397.0 (66.17 %)
Ptnml(0-2): [14, 29, 94, 75, 88], WL/DD Ratio: 8.40
```

**335-124-141**, N=600, Elo A−B **+116.5 ± 25.0**, nElo +140.0 ± 27.8, draw ratio 31.3%, pentanomial [14, 29, 94, 75, 88]
