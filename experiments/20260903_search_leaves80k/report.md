# Search-leaf 80k at teacher `go nodes 8000`

Date: 2026-09-03. Scale of the 40k mix that won equal-node
([search 40k @ 8000](../20260902_search_leaves40k/report.md)). Uniform
**80 000** `search_leaf` + **80 000** path, same teacher
(`go nodes 8000`, seed 20260814). Candidate is `768×128` from
`--init internal`, `--target-mode wdl --result-weight 0.20
--residualize-extras --augment mirror`
(`nets/nnue_search_leaves80k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Best epoch **32**. Float val MAE vs
search/WDL **181** cp. Deployed C++ MAE vs frozen static **16.48** (N held-out,
`--gate none`) — farther from the clone than the 40k net (9.82).

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search80k | **9-173-18** | **0.477** | **−16 ± 18** | 392353 | 398395 |

Candidate score **0.523**. Interval includes 0 (`elo + err ≈ +2`). 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

Doubling the 8000-node sample did **not** beat the 40k mix (7-170-23, −28 ± 19).
Do not scale this mix toward 160k. The 40k net remains the only 768 that
cleared equal-node; its SPRT was inconclusive. Next one-change: same 40k mix
with **result-weight 0** (search labels only). Do not raise `result-weight`.
King-relative waits on eval H1. No SF18 Elo 2000.
