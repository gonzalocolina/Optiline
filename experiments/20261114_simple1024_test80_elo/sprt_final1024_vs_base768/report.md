# fastchess match — sprt_final1024_vs_base768

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `base768` = `build/nsce` + `tools/configs/baseline.uci`
- Limit: tc 8+0.08; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs base768 (8+0.08, 1t, 16MB, openings_balanced.epd):
Elo: 1107.46 +/- nan, nElo: 5957.31 +/- 39.71
LOS: 100.00 %, DrawRatio: 0.00 %, PairsRatio: inf
Games: 294, Wins: 293, Losses: 0, Draws: 1, Points: 293.5 (99.83 %)
Ptnml(0-2): [0, 0, 0, 1, 146], WL/DD Ratio: -nan
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
```

**293-1-0**, N=294, Elo A−B **+5957.3 ± 39.7**, nElo +5957.3 ± 39.7, draw ratio 0.0%, pentanomial [0, 0, 0, 1, 146]
