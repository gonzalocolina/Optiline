# fastchess match — 20260921_nsceper1_simple_extras_off_screen

- A: `baseline` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/tools/configs/baseline.uci`
- B: `nsceper1_gen0_extras_off` = `/home/gonzalo/Escritorio/Codigo/Optiline/build-per1/nsce` + `/home/gonzalo/Escritorio/Codigo/Optiline/train/candidates/nsceper1_gen0_extras_off.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-21

## Result (A − B)

```text
Results of baseline vs nsceper1_gen0_extras_off (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 83.57 +/- 16.15, nElo: 115.89 +/- 21.53
LOS: 100.00 %, DrawRatio: 53.80 %, PairsRatio: 4.50
Games: 1000, Wins: 566, Losses: 330, Draws: 104, Points: 618.0 (61.80 %)
Ptnml(0-2): [19, 23, 269, 81, 108], WL/DD Ratio: inf
```

**566-104-330**, N=1000, Elo A−B **+83.6 ± 16.1**, nElo +115.9 ± 21.5, draw ratio 53.8%, pentanomial [19, 23, 269, 81, 108]
