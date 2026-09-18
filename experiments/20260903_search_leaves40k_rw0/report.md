# Search-leaf 40k, result-weight 0

Date: 2026-09-03. Same 40 000 `search_leaf` + 40 000 path FENs and teacher
(`go nodes 8000`) as [search 40k](../20260902_search_leaves40k/report.md).
The only training change is **`--result-weight 0`** (search/WDL labels only;
path game results unused). Candidate is `768×128` from `--init internal`,
`--target-mode wdl --residualize-extras --augment mirror`
(`nets/nnue_search_leaves40k_rw0.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Best epoch **32**. Float val MAE vs
search **146** cp (sign accuracy 0.70) — better fit than result-weight 0.20
(188 cp, 0.63). Deployed C++ MAE vs frozen static **16.11**.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k_rw0 | **3-177-20** | **0.458** | **−30 ± 16** | 390894 | 394378 |

Candidate score **0.543**. Interval excludes 0 (`elo + err ≈ −13`). 0 overruns.
`equal_node_clearly_winning`: **PASS**.

## Equal time (SPRT)

100 ms, seed 20260814: **H1** at 490 games, **38-447-5**, LLR +2.97,
candidate 0.534, +23 ± 9. `promotion_gate --stage eval` **PASS**.
([SPRT](../20260903_search_leaves40k_rw0_sprt/report.md))

## Decision

Promote `EvalFile` to this net. Next is SF18 Elo 2000, N≥40.
