# fastchess match — 20261111_symmetric_eval_sprt

- A: `symmetric` = `build-sym/nsce` + `tools/configs/baseline.uci`
- B: `previous` = `/tmp/claude-1000/-home-gonzalo-Escritorio-Codigo-Optiline/e1adda8a-a6fc-4bdd-9511-82c993ba1b01/scratchpad/prev/nsce` + `tools/configs/baseline.uci`
- Limit: 100 ms/move; concurrency 14; openings `openings_balanced.epd` random seed 20261111
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-11

## Result (A − B)

```text
Results of symmetric vs previous (0.1/move, 1t, 16MB, openings_balanced.epd):
Elo: 183.35 +/- 28.64, nElo: 253.02 +/- 32.92
LOS: 100.00 %, DrawRatio: 17.76 %, PairsRatio: 8.26
Games: 428, Wins: 264, Losses: 57, Draws: 107, Points: 317.5 (74.18 %)
Ptnml(0-2): [1, 18, 38, 87, 70], WL/DD Ratio: 37.00
LLR: 2.96 (100.4%) (-2.94, 2.94) [0.00, 5.00]
```

**264-107-57**, N=428, Elo A−B **+183.3 ± 28.6**, nElo +253.0 ± 32.9, draw ratio 17.8%, pentanomial [1, 18, 38, 87, 70]
