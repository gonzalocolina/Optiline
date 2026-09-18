# fastchess match — 20260915_search_leaves80k_rw0_full

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/baseline.uci`
- B: `leaves80k` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/nnue_search_leaves80k_rw0.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs leaves80k (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 1.74 +/- 24.14, nElo: 2.00 +/- 27.80
LOS: 55.62 %, DrawRatio: 38.67 %, PairsRatio: 0.98
Games: 600, Wins: 235, Losses: 232, Draws: 133, Points: 301.5 (50.25 %)
Ptnml(0-2): [42, 51, 116, 44, 47], WL/DD Ratio: 5.11
```

**235-133-232**, N=600, Elo A−B **+1.7 ± 24.1**, nElo +2.0 ± 27.8, draw ratio 38.7%, pentanomial [42, 51, 116, 44, 47]
