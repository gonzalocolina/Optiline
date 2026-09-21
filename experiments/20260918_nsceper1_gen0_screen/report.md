# fastchess match — 20260918_nsceper1_gen0_screen

- A: `baseline` = `build-per1/nsce` + `tools/configs/baseline.uci`
- B: `nsceper1_gen0` = `build-per1/nsce` + `train/candidates/nsceper1_gen0.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-18

## Result (A − B)

```text
Results of baseline vs nsceper1_gen0 (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 474.93 +/- 44.28, nElo: 659.06 +/- 21.53
LOS: 100.00 %, DrawRatio: 11.60 %, PairsRatio: 441.00
Games: 1000, Wins: 937, Losses: 59, Draws: 4, Points: 939.0 (93.90 %)
Ptnml(0-2): [0, 1, 58, 3, 438], WL/DD Ratio: inf
```

**937-4-59**, N=1000, Elo A−B **+474.9 ± 44.3**, nElo +659.1 ± 21.5, draw ratio 11.6%, pentanomial [0, 1, 58, 3, 438]
