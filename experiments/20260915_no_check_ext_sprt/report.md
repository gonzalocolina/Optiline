# fastchess match — 20260915_no_check_ext_sprt

- A: `baseline` = `build/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `no_check_ext` = `build-cand/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260916
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs no_check_ext (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 3.82 +/- 10.19, nElo: 4.66 +/- 12.43
LOS: 76.89 %, DrawRatio: 38.87 %, PairsRatio: 1.02
Games: 3000, Wins: 1169, Losses: 1136, Draws: 695, Points: 1516.5 (50.55 %)
Ptnml(0-2): [171, 283, 583, 268, 195], WL/DD Ratio: 7.10
LLR: -0.44 (-14.8%) (-2.94, 2.94) [0.00, 10.00]
```

**1169-695-1136**, N=3000, Elo A−B **+3.8 ± 10.2**, nElo +4.7 ± 12.4, draw ratio 38.9%, pentanomial [171, 283, 583, 268, 195]
