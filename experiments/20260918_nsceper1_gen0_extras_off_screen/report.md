# fastchess match — 20260918_nsceper1_gen0_extras_off_screen

- A: `baseline` = `build-per1/nsce` + `tools/configs/baseline.uci`
- B: `nsceper1_gen0_extras_off` = `build-per1/nsce` + `train/candidates/nsceper1_gen0_extras_off.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-18

## Result (A − B)

```text
Results of baseline vs nsceper1_gen0_extras_off (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 481.10 +/- 44.61, nElo: 678.21 +/- 21.53
LOS: 100.00 %, DrawRatio: 11.40 %, PairsRatio: inf
Games: 1000, Wins: 939, Losses: 57, Draws: 4, Points: 941.0 (94.10 %)
Ptnml(0-2): [0, 0, 57, 4, 439], WL/DD Ratio: inf
```

**939-4-57**, N=1000, Elo A−B **+481.1 ± 44.6**, nElo +678.2 ± 21.5, draw ratio 11.4%, pentanomial [0, 0, 57, 4, 439]
