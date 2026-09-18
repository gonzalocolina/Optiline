# fastchess match — 20260915_hash32_rw0_full

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/baseline.uci`
- B: `hash32` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/hash32_rw0.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs hash32 (0.1/move, 1t, 16MB - 32MB, openings_balanced.epd):
Elo: 29.60 +/- 23.02, nElo: 35.98 +/- 27.80
LOS: 99.44 %, DrawRatio: 39.33 %, PairsRatio: 1.43
Games: 600, Wins: 255, Losses: 204, Draws: 141, Points: 325.5 (54.25 %)
Ptnml(0-2): [29, 46, 118, 59, 48], WL/DD Ratio: 5.56
```

**255-141-204**, N=600, Elo A−B **+29.6 ± 23.0**, nElo +36.0 ± 27.8, draw ratio 39.3%, pentanomial [29, 46, 118, 59, 48]
