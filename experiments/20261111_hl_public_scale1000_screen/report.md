# fastchess match — 20261111_hl_public_scale1000_screen

- A: `baseline768sym` = `build-sym/nsce` + `tools/configs/baseline.uci`
- B: `hl_public_scale1000` = `build-sym/nsce` + `train/candidates/nsceper1_hl_binpack_extras_off.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20261111
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-11

## Result (A − B)

```text
Results of baseline768sym vs hl_public_scale1000 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -308.24 +/- 36.90, nElo: -378.33 +/- 27.80
LOS: 0.00 %, DrawRatio: 20.33 %, PairsRatio: 0.03
Games: 600, Wins: 68, Losses: 494, Draws: 38, Points: 87.0 (14.50 %)
Ptnml(0-2): [204, 28, 61, 4, 3], WL/DD Ratio: 19.33
```

**68-38-494**, N=600, Elo A−B **-308.2 ± 36.9**, nElo -378.3 ± 27.8, draw ratio 20.3%, pentanomial [204, 28, 61, 4, 3]
