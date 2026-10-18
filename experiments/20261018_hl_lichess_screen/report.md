# fastchess match — 20261018_hl_lichess_screen

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci`
- B: `hl_lichess` = `build/nsce` + `tools/configs/nsceper1_hl_lichess.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_uho.epd` random seed 20261018
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-10-18

## Result (A − B)

```text
Results of baseline vs hl_lichess (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 311.77 +/- 62.61, nElo: 401.64 +/- 48.15
LOS: 100.00 %, DrawRatio: 23.00 %, PairsRatio: 76.00
Games: 200, Wins: 167, Losses: 24, Draws: 9, Points: 171.5 (85.75 %)
Ptnml(0-2): [0, 1, 23, 8, 68], WL/DD Ratio: inf
```

**167-9-24**, N=200, Elo A−B **+311.8 ± 62.6**, nElo +401.6 ± 48.1, draw ratio 23.0%, pentanomial [0, 1, 23, 8, 68]

The 768×128 baseline is ahead of the new HL net. B uses `nets/nsceper1_hl_lichess.bin` with `UseExtras` off. One game stalled and fastchess recovered it. Training notes: [20261018_hl_lichess](../20261018_hl_lichess/report.md).
