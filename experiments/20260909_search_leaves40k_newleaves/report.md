# 40k@8000 from appended 8192 leaves — coin flip

Date: 2026-09-09. Candidate is `768×128` from `--init internal` on **40 000**
uniform `search_leaf` FENs taken only from the **last 36 817 302** jsonl rows
(the 8192 `--append`) plus **40 000** path FENs from games 4097–8192, labeled
`go nodes 8000`, `--target-mode wdl --result-weight 0 --residualize-extras
--augment mirror` (`nets/nnue_search_leaves40k_newleaves.bin`, extras on).
One UCI change: `EvalFile`. Does not overwrite the promoted net.
`baseline.uci` unchanged.

This is not another draw over the 4096 dump (that redraw was 10-180-10).

## Data

Path FENs from the increment: **324 831**. Mix: **80 000** rows
(`train/data/nsce_search_mix_40k_newleaves.jsonl`). WDL only on path.
Teacher: current `baseline.uci`.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Best epoch **31**. Float val MAE vs
search/WDL **147** cp (sign accuracy 0.76). Deployed C++ MAE vs frozen static
**13.74** (N=6894, `--gate none`). MAE is not a promotion signal.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both. Trust `nodes_per_move=25000` in JSON.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k_newleaves | **9-181-10** | **0.498** | **−2 ± 15** | 391396 | 392267 |

Candidate score **0.503**. Interval includes 0. 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

Keep `nets/nnue_search_leaves40k_rw0.bin`. Do not take this net to SF18 Elo
2200. New search leaves from the promoted teacher did not beat the 4096-era
mix. Next is fine-tune from the promoted weights on this mix, not another
from-scratch `--init internal`.
