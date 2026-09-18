# Search-leaf 40k — equal-time SPRT

Date: 2026-09-03. Follow-up to the equal-node win
([search 40k](../20260902_search_leaves40k/report.md)).
One UCI change: `EvalFile=nets/nnue_search_leaves40k.bin`.
`baseline.uci` unchanged.

## SPRT

100 ms, `elo0=-5`, `elo1=+5`, min 40 / max 400, seed 20260814,
`openings_balanced.epd`, pair-level pentanomial.

| Decision | W-D-L (search40k) | Games | LLR | pentanomial |
| --- | ---: | ---: | ---: | --- |
| **inconclusive** | **19-372-9** | 400 | **+0.90** | 0-7-177-15-1 |

Candidate score **0.5125**, **+9 ± 9** Elo. Bounds ±2.94. Did not reach H1.
`promotion_gate --stage eval`: **FAIL** (SPRT not promotion-positive).
Do not promote `EvalFile`. Do not play SF18 Elo 2000.

## Decision

Wins nodes (7-170-23, −28 ± 19 to baseline) and is slightly ahead on the
clock, not enough for ±5 Elo H1 at 93% draws. Next professor is the same
40k+40k sample with **more teacher nodes** (`go nodes 25000`), not a static
clone and not a bigger `--label static` dump. King-bucket extras-off stays a
separate candidate with the same gate.
