# fastchess match — base768_vs_sf18_2200

- A: `base768` = `build/nsce` + `tools/configs/baseline.uci`
- B: `sf18_2200` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_elo2200.uci`
- Limit: 100 ms/move; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of base768 vs sf18_2200 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 207.46 +/- 54.03, nElo: 235.58 +/- 48.15
LOS: 100.00 %, DrawRatio: 38.00 %, PairsRatio: 14.50
Games: 200, Wins: 152, Losses: 45, Draws: 3, Points: 153.5 (76.75 %)
Ptnml(0-2): [3, 1, 38, 2, 56], WL/DD Ratio: inf
```

**152-3-45**, N=200, Elo A−B **+207.5 ± 54.0**, nElo +235.6 ± 48.1, draw ratio 38.0%, pentanomial [3, 1, 38, 2, 56]
