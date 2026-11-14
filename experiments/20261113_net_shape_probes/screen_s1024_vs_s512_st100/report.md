# fastchess match — screen_s1024_vs_s512_st100

- A: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- B: `s512` = `build/nsce` + `train/candidates/nsceper1_probe_s512_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024 vs s512 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 6.95 +/- 25.91, nElo: 10.57 +/- 39.32
LOS: 70.08 %, DrawRatio: 47.33 %, PairsRatio: 1.14
Games: 300, Wins: 98, Losses: 92, Draws: 110, Points: 153.0 (51.00 %)
Ptnml(0-2): [8, 29, 71, 33, 9], WL/DD Ratio: 1.96
```

**98-110-92**, N=300, Elo A−B **+7.0 ± 25.9**, nElo +10.6 ± 39.3, draw ratio 47.3%, pentanomial [8, 29, 71, 33, 9]
