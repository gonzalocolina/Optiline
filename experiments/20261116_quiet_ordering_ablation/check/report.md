# fastchess match — check

- A: `check` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/check.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/killers.uci`
- Limit: 50000 nodes/move; concurrency 2; openings `openings_uho.epd` random seed 20261162
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of check vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 2.08 +/- 3.30, nElo: 5.55 +/- 8.79
LOS: 89.19 %, DrawRatio: 81.13 %, PairsRatio: 1.08
Games: 6000, Wins: 2627, Losses: 2591, Draws: 782, Points: 3018.0 (50.30 %)
Ptnml(0-2): [40, 232, 2434, 240, 54], WL/DD Ratio: 14.70
LLR: 0.76 (25.7%) (-2.94, 2.94) [0.00, 5.00]
```

**2627-782-2591**, N=6000, Elo A−B **+2.1 ± 3.3**, nElo +5.5 ± 8.8, draw ratio 81.1%, pentanomial [40, 232, 2434, 240, 54], SPRT LLR +0.76 → **inconclusive**
