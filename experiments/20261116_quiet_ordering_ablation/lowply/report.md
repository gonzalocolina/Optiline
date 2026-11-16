# fastchess match — lowply

- A: `lowply` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/lowply.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/killers.uci`
- Limit: 50000 nodes/move; concurrency 2; openings `openings_uho.epd` random seed 20261165
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of lowply vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 0.87 +/- 3.24, nElo: 2.36 +/- 8.79
LOS: 70.06 %, DrawRatio: 80.80 %, PairsRatio: 1.05
Games: 6000, Wins: 2600, Losses: 2585, Draws: 815, Points: 3007.5 (50.12 %)
Ptnml(0-2): [39, 242, 2424, 255, 40], WL/DD Ratio: 14.25
LLR: -0.03 (-1.2%) (-2.94, 2.94) [0.00, 5.00]
```

**2600-815-2585**, N=6000, Elo A−B **+0.9 ± 3.2**, nElo +2.4 ± 8.8, draw ratio 80.8%, pentanomial [39, 242, 2424, 255, 40], SPRT LLR -0.03 → **inconclusive**
