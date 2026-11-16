# fastchess match — sprt_100ms

- A: `ordering` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_final/bin/ordering` + `tools/configs/baseline.uci`
- B: `master` = `/home/gonzalo/Optiline/experiments/20261116_quiet_ordering_final/bin/master` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 5; openings `openings_uho.epd` random seed 20261170
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of ordering vs master (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 0.17 +/- 2.95, nElo: 0.52 +/- 8.79
LOS: 54.59 %, DrawRatio: 82.83 %, PairsRatio: 1.06
Games: 6000, Wins: 2590, Losses: 2587, Draws: 823, Points: 3001.5 (50.02 %)
Ptnml(0-2): [33, 217, 2485, 244, 21], WL/DD Ratio: 12.73
LLR: -0.49 (-16.7%) (-2.94, 2.94) [0.00, 5.00]
```

**2590-823-2587**, N=6000, Elo A−B **+0.2 ± 3.0**, nElo +0.5 ± 8.8, draw ratio 82.8%, pentanomial [33, 217, 2485, 244, 21], SPRT LLR -0.49 → **inconclusive**
