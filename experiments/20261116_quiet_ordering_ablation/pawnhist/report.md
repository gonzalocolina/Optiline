# fastchess match — pawnhist

- A: `pawnhist` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/pawnhist.uci`
- B: `base` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/bin/qo` + `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_ablation/killers.uci`
- Limit: 50000 nodes/move; concurrency 2; openings `openings_uho.epd` random seed 20261164
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of pawnhist vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 2.08 +/- 3.20, nElo: 5.72 +/- 8.79
LOS: 89.91 %, DrawRatio: 81.57 %, PairsRatio: 1.11
Games: 6000, Wins: 2600, Losses: 2564, Draws: 836, Points: 3018.0 (50.30 %)
Ptnml(0-2): [37, 225, 2447, 247, 44], WL/DD Ratio: 12.45
LLR: 0.80 (27.2%) (-2.94, 2.94) [0.00, 5.00]
```

**2600-836-2564**, N=6000, Elo A−B **+2.1 ± 3.2**, nElo +5.7 ± 8.8, draw ratio 81.6%, pentanomial [37, 225, 2447, 247, 44], SPRT LLR +0.80 → **inconclusive**
