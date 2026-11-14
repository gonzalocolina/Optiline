# fastchess match — screen_s1024wdl30_vs_s1024_st100

- A: `s1024wdl30` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_wdl30_extras_off.uci`
- B: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_balanced.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024wdl30 vs s1024 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -41.89 +/- 28.96, nElo: -57.57 +/- 39.32
LOS: 0.21 %, DrawRatio: 37.33 %, PairsRatio: 0.59
Games: 300, Wins: 70, Losses: 106, Draws: 124, Points: 132.0 (44.00 %)
Ptnml(0-2): [18, 41, 56, 29, 6], WL/DD Ratio: 1.07
```

**70-124-106**, N=300, Elo A−B **-41.9 ± 29.0**, nElo -57.6 ± 39.3, draw ratio 37.3%, pentanomial [18, 41, 56, 29, 6]
