# fastchess match — screen_final1024_vs_probe_hl

- A: `final1024` = `build/nsce` + `train/candidates/nsceper1_simple1024_test80_extras_off.uci`
- B: `probe_hl` = `build/nsce` + `train/candidates/nsceper1_probe_hl_extras_off.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_balanced.epd` random seed 20261115
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of final1024 vs probe_hl (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 356.64 +/- 40.47, nElo: 567.10 +/- 34.05
LOS: 100.00 %, DrawRatio: 10.00 %, PairsRatio: inf
Games: 400, Wins: 328, Losses: 19, Draws: 53, Points: 354.5 (88.62 %)
Ptnml(0-2): [0, 0, 20, 51, 129], WL/DD Ratio: 19.00
```

**328-53-19**, N=400, Elo A−B **+356.6 ± 40.5**, nElo +567.1 ± 34.0, draw ratio 10.0%, pentanomial [0, 0, 20, 51, 129]
