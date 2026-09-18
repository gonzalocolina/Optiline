# fastchess match — 20260915_wdl_leaves640k_full

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/baseline.uci`
- B: `leaves640k` = `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce` + `tools/configs/nnue_wdl_leaves640k.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs leaves640k (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 199.45 +/- 28.59, nElo: 240.44 +/- 27.80
LOS: 100.00 %, DrawRatio: 23.33 %, PairsRatio: 8.58
Games: 600, Wins: 400, Losses: 89, Draws: 111, Points: 455.5 (75.92 %)
Ptnml(0-2): [7, 17, 70, 70, 136], WL/DD Ratio: 4.83
```

**400-111-89**, N=600, Elo A−B **+199.4 ± 28.6**, nElo +240.4 ± 27.8, draw ratio 23.3%, pentanomial [7, 17, 70, 70, 136]
