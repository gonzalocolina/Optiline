# fastchess match — 20261018_hl_gen0_newsearch

- A: `baseline` = `build/nsce` + `tools/configs/baseline.uci`
- B: `hl_gen0` = `build/nsce` + `tools/configs/nsceper1_hl_gen0.uci`
- Limit: 100 ms/move; concurrency 4; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-10-18

## Result (A − B)

```text
Results of baseline vs hl_gen0 (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 294.61 +/- 25.31, nElo: 391.06 +/- 21.53
LOS: 100.00 %, DrawRatio: 25.80 %, PairsRatio: inf
Games: 1000, Wins: 819, Losses: 129, Draws: 52, Points: 845.0 (84.50 %)
Ptnml(0-2): [0, 0, 129, 52, 319], WL/DD Ratio: inf
```

**819-52-129**, N=1000, Elo A−B **+294.6 ± 25.3**, nElo +391.1 ± 21.5, draw ratio 25.8%, pentanomial [0, 0, 129, 52, 319]

The 768×128 baseline is the stronger net on the current search.

Both sides are the same binary, built from `66e0908` (search at `c7cfbcd`). The only UCI difference is `EvalFile`. `nets/nsceper1_gen0.bin` is the HL graph `(768→512)×2 → 32 → 1` from the 23 Sep screen: 853228 bytes, SHA-256 `1f22c4ef667bedef088c41133dc594e86cbdf09dfae63677488a97e7d078899a`. `tools/configs/nsceper1_hl_gen0.uci` hashes to `1cd7631ced375296f8e41ca97e2575113b9aaedbdf86d105b589f37c6b12cfd5`, the same candidate config as that screen. Book, seed, 100 ms, and adjudication match it. This machine ran 4 games at a time.

Five games stalled (baseline 2, HL 3). Fastchess recovered them. The PGN has 1000 finished games. On both sides, fastchess often warned that `bestmove` disagreed with the first move of the last PV. Games still ended by mate or adjudication.

The 23 Sep screen of this same net, on the search from before the rewrite, was **810-60-130**, **+288.1 ± 24.9**. This measurement replaces it.
