# fastchess match — 20260915_evalscale926_full

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/baseline.uci`
- B: `evalscale926` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/evalscale_926.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs evalscale926 (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -0.58 +/- 21.41, nElo: -0.75 +/- 27.80
LOS: 47.88 %, DrawRatio: 42.67 %, PairsRatio: 1.07
Games: 600, Wins: 225, Losses: 226, Draws: 149, Points: 299.5 (49.92 %)
Ptnml(0-2): [34, 49, 128, 62, 27], WL/DD Ratio: 5.74
```

**225-149-226**, N=600, Elo A−B **-0.6 ± 21.4**, nElo -0.8 ± 27.8, draw ratio 42.7%, pentanomial [34, 49, 128, 62, 27]
