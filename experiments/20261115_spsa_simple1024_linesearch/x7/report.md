# fastchess match — x7

- A: `x7` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/x7` + `tools/configs/baseline.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 50000 nodes/move; concurrency 3; openings `openings_uho.epd` random seed 20261122
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of x7 vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 14.56 +/- 7.02, nElo: 35.33 +/- 17.02
LOS: 100.00 %, DrawRatio: 78.50 %, PairsRatio: 1.92
Games: 1600, Wins: 726, Losses: 659, Draws: 215, Points: 833.5 (52.09 %)
Ptnml(0-2): [11, 48, 628, 89, 24], WL/DD Ratio: 15.10
```

**726-215-659**, N=1600, Elo A−B **+14.6 ± 7.0**, nElo +35.3 ± 17.0, draw ratio 78.5%, pentanomial [11, 48, 628, 89, 24]
