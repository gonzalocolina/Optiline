# fastchess match — killers

- A: `killers` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/killers.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/master` + `tools/configs/baseline.uci`
- Limit: 50000 nodes/move; concurrency 2; openings `openings_uho.epd` random seed 20261161
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of killers vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: -0.52 +/- 3.35, nElo: -1.37 +/- 8.79
LOS: 38.01 %, DrawRatio: 81.43 %, PairsRatio: 0.96
Games: 6000, Wins: 2611, Losses: 2620, Draws: 769, Points: 2995.5 (49.93 %)
Ptnml(0-2): [51, 233, 2443, 220, 53], WL/DD Ratio: 14.46
LLR: -0.96 (-32.7%) (-2.94, 2.94) [0.00, 5.00]
```

**2611-769-2620**, N=6000, Elo A−B **-0.5 ± 3.4**, nElo -1.4 ± 8.8, draw ratio 81.4%, pentanomial [51, 233, 2443, 220, 53], SPRT LLR -0.96 → **inconclusive**
