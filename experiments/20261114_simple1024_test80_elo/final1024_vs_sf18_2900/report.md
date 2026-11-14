# fastchess match — final1024_vs_sf18_2900

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `sf18_2900` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_elo2900.uci`
- Limit: 100 ms/move; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs sf18_2900 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 124.99 +/- 42.88, nElo: 153.86 +/- 48.15
LOS: 100.00 %, DrawRatio: 30.00 %, PairsRatio: 4.83
Games: 200, Wins: 109, Losses: 40, Draws: 51, Points: 134.5 (67.25 %)
Ptnml(0-2): [5, 7, 30, 30, 28], WL/DD Ratio: 3.29
```

**109-51-40**, N=200, Elo A−B **+125.0 ± 42.9**, nElo +153.9 ± 48.1, draw ratio 30.0%, pentanomial [5, 7, 30, 30, 28]
