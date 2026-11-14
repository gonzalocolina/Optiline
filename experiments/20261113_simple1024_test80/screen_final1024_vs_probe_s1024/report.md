# fastchess match — screen_final1024_vs_probe_s1024

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `probe_s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_balanced.epd` random seed 20261115
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs probe_s1024 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 120.09 +/- 23.69, nElo: 187.06 +/- 34.05
LOS: 100.00 %, DrawRatio: 30.50 %, PairsRatio: 5.95
Games: 400, Wins: 179, Losses: 46, Draws: 175, Points: 266.5 (66.62 %)
Ptnml(0-2): [0, 20, 61, 85, 34], WL/DD Ratio: 0.74
```

**179-175-46**, N=400, Elo A−B **+120.1 ± 23.7**, nElo +187.1 ± 34.0, draw ratio 30.5%, pentanomial [0, 20, 61, 85, 34]
