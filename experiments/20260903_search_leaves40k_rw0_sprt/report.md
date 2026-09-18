# Search-leaf 40k result-weight 0 — equal-time SPRT H1

Date: 2026-09-03. Follow-up to the equal-node win
([search 40k rw0](../20260903_search_leaves40k_rw0/report.md)).
One UCI change: `EvalFile=nets/nnue_search_leaves40k_rw0.bin`.
`baseline.uci` is promoted after this H1.

## SPRT

100 ms, `elo0=-5`, `elo1=+5`, min 40, seed 20260814,
`openings_balanced.epd`, pair-level pentanomial.

| Cap | Decision | W-D-L (search40k_rw0) | Games | LLR | pentanomial |
| --- | --- | ---: | ---: | ---: | --- |
| 400 | inconclusive | 29-366-5 | 400 | +2.16 | 0-4-170-24-2 |
| **800** | **accept_H1_candidate_stronger** | **38-447-5** | **490** | **+2.97** | 0-4-206-33-2 |

Stopped at pair boundary when LLR crossed +2.94. Candidate score **0.534**,
**+23 ± 9** Elo. 400-game snapshot: `sprt_search40k_rw0_max400.json`.
`promotion_gate --stage eval`: **PASS**.

## Decision

Promote `EvalFile` to `nets/nnue_search_leaves40k_rw0.bin`. Next is SF18 Elo
2000, N≥40, 100 ms, pinned `stockfish-18`, NSCE status oracle. Do not play
unrestricted SF. King-relative is allowed only after this eval H1, and only
after the 2000 rung is measured.
