# fastchess match — 20260923_nsceper1_hl_l1small_screen

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `nsceper1_hl_l1small` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `train/candidates/nsceper1_gen0.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-23

## Result (A − B)

```text
Results of baseline vs nsceper1_hl_l1small (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 288.06 +/- 24.90, nElo: 381.65 +/- 21.53
LOS: 100.00 %, DrawRatio: 25.60 %, PairsRatio: 371.00
Games: 1000, Wins: 810, Losses: 130, Draws: 60, Points: 840.0 (84.00 %)
Ptnml(0-2): [1, 0, 128, 60, 311], WL/DD Ratio: inf
```

**810-60-130**, N=1000, Elo A−B **+288.1 ± 24.9**, nElo +381.6 ± 21.5, draw ratio 25.6%, pentanomial [1, 0, 128, 60, 311]
