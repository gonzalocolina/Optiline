# fastchess match — screen_s1024_vs_s512

- A: `s1024` = `build/nsce` + `train/candidates/nsceper1_probe_s1024_extras_off.uci`
- B: `s512` = `build/nsce` + `train/candidates/nsceper1_probe_s512_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_uho.epd` random seed 20261113
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of s1024 vs s512 (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: -8.69 +/- 20.68, nElo: -20.26 +/- 48.15
LOS: 20.47 %, DrawRatio: 81.00 %, PairsRatio: 0.73
Games: 200, Wins: 84, Losses: 89, Draws: 27, Points: 97.5 (48.75 %)
Ptnml(0-2): [4, 7, 81, 6, 2], WL/DD Ratio: 10.57
```

**84-27-89**, N=200, Elo A−B **-8.7 ± 20.7**, nElo -20.3 ± 48.1, draw ratio 81.0%, pentanomial [4, 7, 81, 6, 2]
