# fastchess match — final1024_vs_sf18_2600

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `sf18_2600` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_elo2600.uci`
- Limit: 100 ms/move; concurrency 10; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs sf18_2600 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 603.86 +/- 155.70, nElo: 1072.08 +/- 48.15
LOS: 100.00 %, DrawRatio: 4.00 %, PairsRatio: inf
Games: 200, Wins: 192, Losses: 4, Draws: 4, Points: 194.0 (97.00 %)
Ptnml(0-2): [0, 0, 4, 4, 92], WL/DD Ratio: inf
```

**192-4-4**, N=200, Elo A−B **+603.9 ± 155.7**, nElo +1072.1 ± 48.1, draw ratio 4.0%, pentanomial [0, 0, 4, 4, 92]
