# fastchess match — 20261018_hl_full_screen

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci`
- B: `hl_full` = `build/nsce` + `tools/configs/nsceper1_hl_full.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_uho.epd` random seed 20261018
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-10-18

## Result (A − B)

```text
Results of baseline vs hl_full (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 159.78 +/- 43.36, nElo: 205.17 +/- 48.15
LOS: 100.00 %, DrawRatio: 46.00 %, PairsRatio: 12.50
Games: 200, Wins: 137, Losses: 51, Draws: 12, Points: 143.0 (71.50 %)
Ptnml(0-2): [1, 3, 46, 9, 41], WL/DD Ratio: inf
```

**137-12-51**, N=200, Elo A−B **+159.8 ± 43.4**, nElo +205.2 ± 48.1, draw ratio 46.0%, pentanomial [1, 3, 46, 9, 41]

The 768×128 baseline is still ahead. The same screen of the 12-epoch run that had killed the SCReLU units was **167-9-24**, **+311.8 ± 62.6**, draw ratio 23%. This net draws more and loses about 150 Elo less. Training notes: [20261018_hl_full](../20261018_hl_full/report.md).
