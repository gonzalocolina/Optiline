# fastchess match — sprt_x7_100ms

- A: `x7` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/x7` + `tools/configs/baseline.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_uho.epd` random seed 20261117
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of x7 vs base (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 6.95 +/- 3.66, nElo: 20.21 +/- 10.64
LOS: 99.99 %, DrawRatio: 82.48 %, PairsRatio: 1.55
Games: 4098, Wins: 1805, Losses: 1723, Draws: 570, Points: 2090.0 (51.00 %)
Ptnml(0-2): [19, 122, 1690, 194, 24], WL/DD Ratio: 12.31
LLR: 2.97 (100.8%) (-2.94, 2.94) [0.00, 5.00]
```

**1805-570-1723**, N=4098, Elo A−B **+7.0 ± 3.7**, nElo +20.2 ± 10.6, draw ratio 82.5%, pentanomial [19, 122, 1690, 194, 24], SPRT LLR +2.97 → **H1**
