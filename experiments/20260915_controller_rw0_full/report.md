# fastchess match — 20260915_controller_rw0_full

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci`
- B: `controller` = `build/nsce` + `tools/configs/controller_rw0.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs controller (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 9.27 +/- 23.12, nElo: 11.17 +/- 27.80
LOS: 78.44 %, DrawRatio: 39.00 %, PairsRatio: 1.15
Games: 600, Wins: 239, Losses: 223, Draws: 138, Points: 308.0 (51.33 %)
Ptnml(0-2): [37, 48, 117, 58, 40], WL/DD Ratio: 6.31
```

**239-138-223**, N=600, Elo A−B **+9.3 ± 23.1**, nElo +11.2 ± 27.8, draw ratio 39.0%, pentanomial [37, 48, 117, 58, 40]
