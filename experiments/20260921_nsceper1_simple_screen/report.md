# fastchess match — 20260921_nsceper1_simple_screen

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `nsceper1_gen0` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/train/candidates/nsceper1_gen0.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-21

## Result (A − B)

```text
Results of baseline vs nsceper1_gen0 (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 100.33 +/- 16.37, nElo: 139.60 +/- 21.53
LOS: 100.00 %, DrawRatio: 49.80 %, PairsRatio: 6.38
Games: 1000, Wins: 579, Losses: 298, Draws: 123, Points: 640.5 (64.05 %)
Ptnml(0-2): [17, 17, 249, 102, 115], WL/DD Ratio: 123.50
```

**579-123-298**, N=1000, Elo A−B **+100.3 ± 16.4**, nElo +139.6 ± 21.5, draw ratio 49.8%, pentanomial [17, 17, 249, 102, 115]
