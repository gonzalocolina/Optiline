# fastchess match — 20260915_no_check_ext

- A: `baseline` = `build/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `no_check_ext` = `build-cand/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-15

## Result (A − B)

```text
Results of baseline vs no_check_ext (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: -22.62 +/- 23.39, nElo: -26.99 +/- 27.80
LOS: 2.85 %, DrawRatio: 39.33 %, PairsRatio: 0.72
Games: 600, Wins: 213, Losses: 252, Draws: 135, Points: 280.5 (46.75 %)
Ptnml(0-2): [45, 61, 118, 40, 36], WL/DD Ratio: 5.94
```

**213-135-252**, N=600, Elo A−B **-22.6 ± 23.4**, nElo -27.0 ± 27.8, draw ratio 39.3%, pentanomial [45, 61, 118, 40, 36]
