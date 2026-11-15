# fastchess match — x2

- A: `x2` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/x2` + `tools/configs/baseline.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 50000 nodes/move; concurrency 3; openings `openings_uho.epd` random seed 20261117
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of x2 vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 7.60 +/- 6.86, nElo: 18.87 +/- 17.02
LOS: 98.51 %, DrawRatio: 79.00 %, PairsRatio: 1.58
Games: 1600, Wins: 717, Losses: 682, Draws: 201, Points: 817.5 (51.09 %)
Ptnml(0-2): [17, 48, 632, 89, 14], WL/DD Ratio: 18.75
```

**717-201-682**, N=1600, Elo A−B **+7.6 ± 6.9**, nElo +18.9 ± 17.0, draw ratio 79.0%, pentanomial [17, 48, 632, 89, 14]
