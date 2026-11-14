# fastchess match — final1024_vs_sf18_unlimited

- A: `final1024` = `build/nsce` + `tools/configs/nsceper1_simple1024.uci`
- B: `sf18` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_unlimited.uci`
- Limit: 100 ms/move; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs sf18 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -322.67 +/- 64.44, nElo: -590.95 +/- 68.10
LOS: 0.00 %, DrawRatio: 6.00 %, PairsRatio: 0.00
Games: 100, Wins: 1, Losses: 74, Draws: 25, Points: 13.5 (13.50 %)
Ptnml(0-2): [26, 21, 3, 0, 0], WL/DD Ratio: 0.50
```

**1-25-74**, N=100, Elo A−B **-322.7 ± 64.4**, nElo -591.0 ± 68.1, draw ratio 6.0%, pentanomial [26, 21, 3, 0, 0]
