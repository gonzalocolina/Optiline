# fastchess match — sprt_100ms

- A: `ordering` = `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/bin/new` + `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/tuned.uci`
- B: `head` = `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/bin/head` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 5; openings `openings_uho.epd` random seed 20261118
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of ordering vs head (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 0.75 +/- 3.08, nElo: 2.15 +/- 8.79
LOS: 68.42 %, DrawRatio: 82.30 %, PairsRatio: 1.05
Games: 6000, Wins: 2588, Losses: 2575, Draws: 837, Points: 3006.5 (50.11 %)
Ptnml(0-2): [34, 225, 2469, 238, 34], WL/DD Ratio: 12.20
LLR: -0.09 (-3.0%) (-2.94, 2.94) [0.00, 5.00]
```

**2588-837-2575**, N=6000, Elo A−B **+0.8 ± 3.1**, nElo +2.1 ± 8.8, draw ratio 82.3%, pentanomial [34, 225, 2469, 238, 34], SPRT LLR -0.09 → **inconclusive**
