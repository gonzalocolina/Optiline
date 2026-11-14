# fastchess match — screen_s1024_vs_hl

- A: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- B: `hl` = `build/nsce` + `train/candidates/nsceper1_probe_hl_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_uho.epd` random seed 20261113
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024 vs hl (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 128.95 +/- 35.58, nElo: 191.93 +/- 48.15
LOS: 100.00 %, DrawRatio: 54.00 %, PairsRatio: 22.00
Games: 200, Wins: 125, Losses: 54, Draws: 21, Points: 135.5 (67.75 %)
Ptnml(0-2): [0, 2, 54, 15, 29], WL/DD Ratio: 26.00
```

**125-21-54**, N=200, Elo A−B **+128.9 ± 35.6**, nElo +191.9 ± 48.1, draw ratio 54.0%, pentanomial [0, 2, 54, 15, 29]
