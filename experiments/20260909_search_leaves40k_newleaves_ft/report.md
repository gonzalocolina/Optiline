# Fine-tune promoted 768 on appended-8192 mix — coin flip

Date: 2026-09-09. Same 40k@8000 new-leaf mix as
[newleaves](../20260909_search_leaves40k_newleaves/report.md). The only
training change is **`--init nets/nnue_search_leaves40k_rw0.bin`** instead of
`--init internal`. Candidate `nets/nnue_search_leaves40k_newleaves_ft.bin`,
extras on, result-weight 0. One UCI change: `EvalFile`. Does not overwrite
the promoted net. `baseline.uci` unchanged.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Epoch 0 (promoted weights) float MAE
**148**. Best epoch **31**, float MAE **146**. Deployed C++ MAE vs frozen
static **15.27** (N=6894, `--gate none`). MAE is not a promotion signal.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both. Trust `nodes_per_move=25000` in JSON.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k_newleaves_ft | **5-186-9** | **0.490** | **−7 ± 13** | 392617 | 396859 |

Candidate score **0.510**. Interval includes 0 (`elo + err > 0`). 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

Keep `nets/nnue_search_leaves40k_rw0.bin`. New leaves, from-scratch or
fine-tune, do not beat this 768 at equal-node. Do not take this net to SF18
Elo 2200. Next 2200 work is a larger sample of the **promoted** engine vs
pinned SF18 Elo 2200 (N=80 was +22 ± 64).
