# fastchess match — screen_final1024_vs_base768

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `base768` = `build/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_balanced.epd` random seed 20261115
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs base768 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 726.94 +/- 132.94, nElo: 1724.31 +/- 34.05
LOS: 100.00 %, DrawRatio: 1.00 %, PairsRatio: inf
Games: 400, Wins: 390, Losses: 2, Draws: 8, Points: 394.0 (98.50 %)
Ptnml(0-2): [0, 0, 2, 8, 190], WL/DD Ratio: inf
```

**390-8-2**, N=400, Elo A−B **+726.9 ± 132.9**, nElo +1724.3 ± 34.0, draw ratio 1.0%, pentanomial [0, 0, 2, 8, 190]
