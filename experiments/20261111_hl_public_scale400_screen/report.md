# fastchess match — 20261111_hl_public_scale400_screen

- A: `baseline768sym` = `build-sym/nsce` + `tools/configs/baseline.uci`
- B: `hl_public_scale400` = `build-sym/nsce` + `train/candidates/nsceper1_hl_binpack_extras_off_scale400.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20261111
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-11

## Result (A − B)

```text
Results of baseline768sym vs hl_public_scale400 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -291.32 +/- 34.61, nElo: -362.99 +/- 27.80
LOS: 0.00 %, DrawRatio: 22.33 %, PairsRatio: 0.03
Games: 600, Wins: 76, Losses: 487, Draws: 37, Points: 94.5 (15.75 %)
Ptnml(0-2): [194, 32, 67, 5, 2], WL/DD Ratio: inf
```

**76-37-487**, N=600, Elo A−B **-291.3 ± 34.6**, nElo -363.0 ± 27.8, draw ratio 22.3%, pentanomial [194, 32, 67, 5, 2]
