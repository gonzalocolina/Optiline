# fastchess match — 20260915_instrument_internal_full

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `internal` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/baseline_internal.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs internal (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 145.13 +/- 45.04, nElo: 175.29 +/- 48.15
LOS: 100.00 %, DrawRatio: 32.00 %, PairsRatio: 6.56
Games: 200, Wins: 123, Losses: 44, Draws: 33, Points: 139.5 (69.75 %)
Ptnml(0-2): [5, 4, 32, 25, 34], WL/DD Ratio: 15.00
```

**123-33-44**, N=200, Elo A−B **+145.1 ± 45.0**, nElo +175.3 ± 48.1, draw ratio 32.0%, pentanomial [5, 4, 32, 25, 34]
