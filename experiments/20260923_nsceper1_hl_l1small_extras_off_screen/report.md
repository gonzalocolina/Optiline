# fastchess match — 20260923_nsceper1_hl_l1small_extras_off_screen

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `nsceper1_hl_l1small_extras_off` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `train/candidates/nsceper1_gen0_extras_off.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-23

## Result (A − B)

```text
Results of baseline vs nsceper1_hl_l1small_extras_off (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 266.97 +/- 23.38, nElo: 356.05 +/- 21.53
LOS: 100.00 %, DrawRatio: 27.00 %, PairsRatio: 120.67
Games: 1000, Wins: 784, Losses: 138, Draws: 78, Points: 823.0 (82.30 %)
Ptnml(0-2): [1, 2, 135, 74, 288], WL/DD Ratio: 134.00
```

**784-78-138**, N=1000, Elo A−B **+267.0 ± 23.4**, nElo +356.1 ± 21.5, draw ratio 27.0%, pentanomial [1, 2, 135, 74, 288]
