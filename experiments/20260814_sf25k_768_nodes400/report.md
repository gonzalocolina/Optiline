# SF 25k-node 768: MAE win, equal-node loss (N=400)

Date: 2026-08-14. Candidate `nets/nnue_sf25k.bin` (768×128 from internal,
extras off) vs frozen baseline (internal + extras). Stockfish `go nodes 25000`
labels on the same 200k FENs as the closed NSCE self-distill. MAE gate passed
(113.0 vs 143.6). Search-Elo gate follows.

## Equal node (`go nodes 25000`)

N=40 was exploratory (±50 Elo, CI includes 0). Confirmatory N=400, same seed
20260814 (first 40 pairs nested), ~7.5 min.

| N | W-D-L (baseline) | Score A | Elo A−B ±95% | cand. score | Path |
| ---: | --- | ---: | ---: | ---: | --- |
| 40 | 5-32-3 | 0.525 | +17 ± 50 | 0.475 | [nodes](../20260814_sf25k_768_nodes/report.md) |
| **400** | **43-338-19** | **0.530** | **+21 ± 13** | **0.470** | this dir |

- A: `tools/configs/baseline.uci` (internal + extras)
- B: `tools/configs/nnue_sf25k.uci` (768, extras off)
- Openings: `openings_balanced.epd`, max plies 60, 0 overruns
- Nodes/game: baseline 394k, candidate 406k
- Time/game: baseline 595 ms, candidate 472 ms (candidate **faster**; extras() is the time tax)

Need challenger score clearly > 0.5. **Fail.** CI at N=400 excludes 0: baseline
is about **+21 Elo** at equal nodes. **No 100 ms SPRT. `baseline.uci` unchanged.**

## Pruning off (RFP / razor / futility false on both)

Same 25k nodes, seed, N=400: baseline **44-332-24**, score 0.525, **+17 ± 14**.
Candidate still loses. The gap is the eval as a search companion, not the
interaction with those three prunes. ([noprune400](../20260814_sf25k_768_noprune400/report.md))

## Tree shape (`go depth 10`, 6 bench FENs)

Totals: candidate **0.47×** nodes, **1.38×** nps vs baseline. Kiwipete dominates
the sum (baseline 3.82M / 5.70M). Startpos is **2.20×** bushier — same qualitative
hole as Lichess KAT. Aggregate “narrower tree” is not a search-Elo win.
([prune](../20260814_sf25k_768_prune/report.md))

Better leaf MAE on Stockfish search-cp did not make a stronger search companion.
Do not replay `nnue_sf25k.bin` at 100 ms. Do not raise `kHidden` on this net.
