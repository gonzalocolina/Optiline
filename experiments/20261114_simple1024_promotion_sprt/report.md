# fastchess match — 20261114_simple1024_promotion_sprt

- A: `base768` = `build/nsce` + `tools/configs/baseline.uci`
- B: `simple1024` = `build/nsce` + `tools/configs/nsceper1_simple1024.uci`
- Limit: tc 8+0.08; concurrency 10; openings `openings_uho.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-14

## Result (A − B)

```text
Results of base768 vs simple1024 (8+0.08, 1t, 16MB, openings_uho.epd):
Elo: -158.62 +/- 27.48, nElo: -215.22 +/- 32.46
LOS: 0.00 %, DrawRatio: 55.91 %, PairsRatio: 0.00
Games: 440, Wins: 123, Losses: 311, Draws: 6, Points: 126.0 (28.64 %)
Ptnml(0-2): [91, 6, 123, 0, 0], WL/DD Ratio: inf
LLR: -2.97 (-100.7%) (-2.94, 2.94) [0.00, 5.00]
```

**123-6-311**, N=440, Elo A−B **-158.6 ± 27.5**, nElo -215.2 ± 32.5, draw ratio 55.9%, pentanomial [91, 6, 123, 0, 0]
