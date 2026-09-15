# fastchess match — 20260915_nps_movepicker_time_full

- A: `frozen` = `build/nsce-frozen-20260915` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `movepicker` = `build-nps/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of frozen vs movepicker (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 47.78 +/- 31.28, nElo: 61.00 +/- 39.32
LOS: 99.88 %, DrawRatio: 41.33 %, PairsRatio: 1.93
Games: 300, Wins: 134, Losses: 93, Draws: 73, Points: 170.5 (56.83 %)
Ptnml(0-2): [11, 19, 62, 34, 24], WL/DD Ratio: 5.20
```

**134-73-93**, N=300, Elo A−B **+47.8 ± 31.3**, nElo +61.0 ± 39.3, draw ratio 41.3%, pentanomial [11, 19, 62, 34, 24]
