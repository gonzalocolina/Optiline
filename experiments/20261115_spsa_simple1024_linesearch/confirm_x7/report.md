# fastchess match — confirm_x7

- A: `x7` = `experiments/20261115_spsa_simple1024_linesearch/bin/x7` + `tools/configs/baseline.uci`
- B: `base` = `experiments/20261115_spsa_simple1024_linesearch/bin/base` + `tools/configs/baseline.uci`
- Limit: 50000 nodes/move; concurrency 9; openings `openings_uho.epd` random seed 77115
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-15

## Result (A − B)

```text
Results of x7 vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 13.94 +/- 5.71, nElo: 34.76 +/- 14.22
LOS: 100.00 %, DrawRatio: 79.77 %, PairsRatio: 2.01
Games: 2294, Wins: 1049, Losses: 957, Draws: 288, Points: 1193.0 (52.01 %)
Ptnml(0-2): [17, 60, 915, 124, 31], WL/DD Ratio: 16.60
LLR: 2.98 (101.1%) (-2.94, 2.94) [0.00, 5.00]
```

**1049-288-957**, N=2294, Elo A−B **+13.9 ± 5.7**, nElo +34.8 ± 14.2, draw ratio 79.8%, pentanomial [17, 60, 915, 124, 31], SPRT LLR +2.98 → **H1 accepted** (fastchess: "SPRT ([0.00, 5.00]) completed - H1 was accepted"; the report first said inconclusive because of a parser bug fixed in tools/fastchess_match.py)
