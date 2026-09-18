# Search-leaf 80k result-weight 0 vs promoted 40k

Date: 2026-09-04. Same 80 000 `search_leaf` + 80 000 path FENs at
`go nodes 8000` as [search 80k rw 0.20](../20260903_search_leaves80k/report.md),
retrained with **`--result-weight 0`** (the recipe that promoted at 40k).
Candidate: `nets/nnue_search_leaves80k_rw0.bin`, extras on. One UCI change:
`EvalFile`. Opponent is the **promoted** baseline
(`EvalFile=nets/nnue_search_leaves40k_rw0.bin`).

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch **32**. Float val MAE vs search **142** cp (sign accuracy 0.70).
Deployed C++ MAE vs frozen static **18.26**.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| promoted 40k vs search80k_rw0 | **9-180-11** | **0.495** | **−3 ± 16** | 391698 | 397385 |

Candidate score **0.505**. Interval includes 0. 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

Doubling the search mix at result-weight 0 does not beat the promoted 40k net.
Do not scale this 768 further as the Elo path to 2200. Keep
`nets/nnue_search_leaves40k_rw0.bin`. SF18 Elo 2200 N=80 remains
30-25-25, +22 ± 64 (not ≥2200).
