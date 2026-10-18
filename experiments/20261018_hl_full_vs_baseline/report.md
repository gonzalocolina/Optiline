# fastchess match — 20261018_hl_full_vs_baseline

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci` (`nets/nnue_search_leaves40k_rw0.bin`, 768×128)
- B: `hl_full` = `build/nsce` + `tools/configs/nsceper1_hl_full.uci` (`nets/nsceper1_hl_full.bin`)
- Limit: 100 ms/move; concurrency 4; openings `openings_uho.epd` random seed 20261019
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-10-18

## Result (A − B)

```text
Results of baseline vs hl_full (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 150.51 +/- 18.68, nElo: 196.37 +/- 21.53
LOS: 100.00 %, DrawRatio: 46.80 %, PairsRatio: 12.30
Games: 1000, Wins: 669, Losses: 261, Draws: 70, Points: 704.0 (70.40 %)
Ptnml(0-2): [7, 13, 234, 57, 189], WL/DD Ratio: inf
```

**669-70-261**, N=1000, Elo A−B **+150.5 ± 18.7**, nElo +196.4 ± 21.5, draw ratio 46.8%, pentanomial [7, 13, 234, 57, 189]

The 768×128 baseline is the stronger net. One game stalled and fastchess recovered it. A 200-game probe of this same pair was +159.8 ± 43.4. The HL net whose units had died lost the 200-game screen by +311.8 ± 62.6.
