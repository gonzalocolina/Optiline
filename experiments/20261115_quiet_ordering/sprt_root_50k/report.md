# fastchess match — sprt_root_50k

- A: `rootorder` = `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/bin/new` + `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/tuned.uci`
- B: `noroot` = `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/bin/new` + `/home/gonzalo/Optiline/experiments/20261115_quiet_ordering/tuned_noroot.uci`
- Limit: 50000 nodes/move; concurrency 5; openings `openings_uho.epd` random seed 20261119
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-16

## Result (A − B)

```text
Results of rootorder vs noroot (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: -1.16 +/- 3.22, nElo: -3.16 +/- 8.79
LOS: 24.06 %, DrawRatio: 81.73 %, PairsRatio: 0.96
Games: 6000, Wins: 2635, Losses: 2655, Draws: 710, Points: 2990.0 (49.83 %)
Ptnml(0-2): [48, 231, 2452, 231, 38], WL/DD Ratio: 18.77
LLR: -1.41 (-47.8%) (-2.94, 2.94) [0.00, 5.00]
```

**2635-710-2655**, N=6000, Elo A−B **-1.2 ± 3.2**, nElo -3.2 ± 8.8, draw ratio 81.7%, pentanomial [48, 231, 2452, 231, 38], SPRT LLR -1.41 → **inconclusive**
