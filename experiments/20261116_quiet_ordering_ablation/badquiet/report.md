# fastchess match — badquiet

- A: `badquiet` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/badquiet.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/killers.uci`
- Limit: 50000 nodes/move; concurrency 2; openings `openings_uho.epd` random seed 20261163
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of badquiet vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: -2.20 +/- 3.44, nElo: -5.63 +/- 8.79
LOS: 10.48 %, DrawRatio: 80.50 %, PairsRatio: 0.92
Games: 6000, Wins: 2587, Losses: 2625, Draws: 788, Points: 2981.0 (49.68 %)
Ptnml(0-2): [62, 243, 2415, 231, 49], WL/DD Ratio: 14.38
LLR: -2.02 (-68.6%) (-2.94, 2.94) [0.00, 5.00]
```

**2587-788-2625**, N=6000, Elo A−B **-2.2 ± 3.4**, nElo -5.6 ± 8.8, draw ratio 80.5%, pentanomial [62, 243, 2415, 231, 49], SPRT LLR -2.02 → **inconclusive**
