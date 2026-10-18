# fastchess match — 20261018_search_speed_sprt

- A: `speed` = `build/nsce` + `tools/configs/baseline.uci`
- B: `previous` = `/tmp/nsce-prev/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20261018
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-10-18

## Result (A − B)

```text
Results of speed vs previous (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 125.17 +/- 25.63, nElo: 154.78 +/- 29.04
LOS: 100.00 %, DrawRatio: 37.82 %, PairsRatio: 4.52
Games: 550, Wins: 326, Losses: 136, Draws: 88, Points: 370.0 (67.27 %)
Ptnml(0-2): [8, 23, 104, 51, 89], WL/DD Ratio: 13.86
LLR: 2.94 (100.0%) (-2.94, 2.94) [0.00, 5.00]
```

**326-88-136**, N=550, Elo A−B **+125.2 ± 25.6**, nElo +154.8 ± 29.0, draw ratio 37.8%, pentanomial [8, 23, 104, 51, 89]
