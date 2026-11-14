# fastchess match — screen_s1024_vs_base768

- A: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- B: `base768` = `build/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_uho.epd` random seed 20261113
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024 vs base768 (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 188.54 +/- 44.37, nElo: 249.55 +/- 48.15
LOS: 100.00 %, DrawRatio: 48.00 %, PairsRatio: inf
Games: 200, Wins: 147, Losses: 48, Draws: 5, Points: 149.5 (74.75 %)
Ptnml(0-2): [0, 0, 48, 5, 47], WL/DD Ratio: inf
```

**147-5-48**, N=200, Elo A−B **+188.5 ± 44.4**, nElo +249.6 ± 48.1, draw ratio 48.0%, pentanomial [0, 0, 48, 5, 47]
