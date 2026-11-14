# fastchess match — final1024_vs_sf18_3190

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `sf18_3190` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_elo3190.uci`
- Limit: 100 ms/move; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs sf18_3190 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -40.13 +/- 37.26, nElo: -52.53 +/- 48.15
LOS: 1.63 %, DrawRatio: 33.00 %, PairsRatio: 0.68
Games: 200, Wins: 52, Losses: 75, Draws: 73, Points: 88.5 (44.25 %)
Ptnml(0-2): [14, 26, 33, 23, 4], WL/DD Ratio: 1.75
```

**52-73-75**, N=200, Elo A−B **-40.1 ± 37.3**, nElo -52.5 ± 48.1, draw ratio 33.0%, pentanomial [14, 26, 33, 23, 4]
