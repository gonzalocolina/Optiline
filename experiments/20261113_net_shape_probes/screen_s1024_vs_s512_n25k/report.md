# fastchess match — screen_s1024_vs_s512_n25k

- A: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- B: `s512` = `build/nsce` + `train/candidates/nsceper1_probe_s512_extras_off.uci`
- Limit: 25000 nodes/move; concurrency 3; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024 vs s512 (25000 nodes, 1t, 16MB, openings_balanced.epd):
Elo: 44.25 +/- 31.41, nElo: 56.14 +/- 39.32
LOS: 99.74 %, DrawRatio: 36.67 %, PairsRatio: 1.71
Games: 300, Wins: 127, Losses: 89, Draws: 84, Points: 169.0 (56.33 %)
Ptnml(0-2): [10, 25, 55, 37, 23], WL/DD Ratio: 4.00
```

**127-84-89**, N=300, Elo A−B **+44.2 ± 31.4**, nElo +56.1 ± 39.3, draw ratio 36.7%, pentanomial [10, 25, 55, 37, 23]
