# Search-leaf 40k mix — first equal-node win vs this tree

Date: 2026-09-02. First eval candidate whose labels are NSCE **search**
(`go nodes 8000`) on leaves, not `--label static`. Candidate is `768×128`
from `--init internal` on **40 000** uniform `search_leaf` FENs plus
**40 000** path FENs, `--target-mode wdl --result-weight 0.20
--residualize-extras --augment mirror`
(`nets/nnue_search_leaves40k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged. Result-weight was not raised.

Train first crashed (`NameError: _variant_target`) after `pack_active_rows`
replaced that helper; the helper was restored. Mix was not re-distilled.

## Data

Uniform sample (seed 20260814) of **40 000** `search_leaf` and **40 000**
path FENs from the 4096-game corpus. Teacher: frozen `baseline.uci`,
`go nodes 8000`. Mix: **80 000** rows
(`train/data/nsce_search_mix_40k.jsonl`). WDL only on path.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch **10**. Float val MAE vs search/WDL targets **188** cp (sign
accuracy 0.63) — the net did **not** fit the search teacher. Deployed C++
MAE vs the **frozen static** arbiter is **9.82** (N=6737, `--gate none`).
That is a small nudge off the clone, not a clone of search. MAE is not a
promotion signal.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k | **7-170-23** | **0.460** | **−28 ± 19** | 387995 | 393317 |

Candidate score **0.540**. Interval excludes 0 (`elo + err < 0`). 0 overruns.
`equal_node_clearly_winning`: **PASS**. Do not promote `EvalFile` yet.

## Equal time (SPRT)

100 ms, max 400, seed 20260814: **inconclusive** 19-372-9, LLR +0.90,
candidate 0.5125, +9 ± 9. `promotion_gate --stage eval` FAIL.
([SPRT](../20260902_search_leaves40k_sprt/report.md))

## Decision

First 768 mix that beats this tree at equal nodes. Equal-time SPRT did not
accept H1. Do not promote. Next is the same sample with a stronger search
teacher (`go nodes 25000`), not SF18 Elo 2000.
