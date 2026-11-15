# fastchess match — x4

- A: `x4` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/x4` + `tools/configs/baseline.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 50000 nodes/move; concurrency 3; openings `openings_uho.epd` random seed 20261119
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of x4 vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 8.90 +/- 6.27, nElo: 24.18 +/- 17.02
LOS: 99.73 %, DrawRatio: 81.62 %, PairsRatio: 1.49
Games: 1600, Wins: 726, Losses: 685, Draws: 189, Points: 820.5 (51.28 %)
Ptnml(0-2): [6, 53, 653, 70, 18], WL/DD Ratio: 18.79
```

**726-189-685**, N=1600, Elo A−B **+8.9 ± 6.3**, nElo +24.2 ± 17.0, draw ratio 81.6%, pentanomial [6, 53, 653, 70, 18]
