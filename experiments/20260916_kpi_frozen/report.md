# fastchess match — 20260916_kpi_frozen

- A: `current` = `build/nsce` + `tools/configs/baseline.uci`
- B: `frozen` = `build/nsce-frozen-20260915` + `tools/configs/baseline.uci`
- Limit: tc 8+0.08; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-16

## Result (A − B)

```text
Results of current vs frozen (8+0.08, 1t, 16MB, openings_uho.epd):
Elo: 3.47 +/- 20.70, nElo: 6.61 +/- 39.32
LOS: 62.91 %, DrawRatio: 68.67 %, PairsRatio: 1.04
Games: 300, Wins: 129, Losses: 126, Draws: 45, Points: 151.5 (50.50 %)
Ptnml(0-2): [5, 18, 103, 17, 7], WL/DD Ratio: 19.60
```

**129-45-126**, N=300, Elo A−B **+3.5 ± 20.7**, nElo +6.6 ± 39.3, draw ratio 68.7%, pentanomial [5, 18, 103, 17, 7]
