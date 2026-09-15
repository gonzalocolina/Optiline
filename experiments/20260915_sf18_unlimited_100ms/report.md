# fastchess match — 20260915_sf18_unlimited_100ms

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `sf18` = `third_party/stockfish/stockfish-18` + `tools/configs/sf18_unlimited.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs sf18 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -919.54 +/- nan, nElo: -3474.53 +/- 68.10
LOS: 0.00 %, DrawRatio: 0.00 %, PairsRatio: 0.00
Games: 100, Wins: 0, Losses: 99, Draws: 1, Points: 0.5 (0.50 %)
Ptnml(0-2): [49, 1, 0, 0, 0], WL/DD Ratio: -nan
```

**0-1-99**, N=100, Elo A−B **-3474.5 ± 68.1**, nElo -3474.5 ± 68.1, draw ratio 0.0%, pentanomial [49, 1, 0, 0, 0]
