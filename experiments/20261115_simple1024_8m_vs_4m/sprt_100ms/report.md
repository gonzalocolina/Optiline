# fastchess match — sprt_100ms

- A: `net8m` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `train/candidates/nsceper1_simple1024_8m_extras_off.uci`
- B: `net4m` = `/home/gonzalo/Optiline/experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 3; openings `openings_uho.epd` random seed 20261116
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of net8m vs net4m (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 2.03 +/- 3.29, nElo: 5.41 +/- 8.79
LOS: 88.63 %, DrawRatio: 80.87 %, PairsRatio: 1.06
Games: 6000, Wins: 2619, Losses: 2584, Draws: 797, Points: 3017.5 (50.29 %)
Ptnml(0-2): [35, 244, 2426, 241, 54], WL/DD Ratio: 14.55
LLR: 0.73 (24.7%) (-2.94, 2.94) [0.00, 5.00]
```

**2619-797-2584**, N=6000, Elo A−B **+2.0 ± 3.3**, nElo +5.4 ± 8.8, draw ratio 80.9%, pentanomial [35, 244, 2426, 241, 54], SPRT LLR +0.73 → **inconclusive**
