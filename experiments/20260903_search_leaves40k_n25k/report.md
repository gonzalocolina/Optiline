# Search-leaf 40k at teacher `go nodes 25000`

Date: 2026-09-03. Same 40 000 `search_leaf` + 40 000 path FENs as
[search 40k @ 8000](../20260902_search_leaves40k/report.md), relabeled with
frozen `baseline.uci` `go nodes 25000`. Candidate is `768×128` from
`--init internal`, `--target-mode wdl --result-weight 0.20
--residualize-extras --augment mirror`
(`nets/nnue_search_leaves40k_n25k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Best epoch **18**. Float val MAE vs
search/WDL **202** cp. Deployed C++ MAE vs frozen static **11.40** (N=6737,
`--gate none`). Closer to the clone than the 8000-node net (9.82). MAE is not
a promotion signal.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k_n25k | **6-180-14** | **0.480** | **−14 ± 15** | 395678 | 402877 |

Candidate score **0.520**. Interval includes 0 (`elo + err = +1`). 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

A stronger teacher on the same 40k sample did **not** beat the 8000-node mix
(that one was 7-170-23, −28 ± 19, interval excluded 0). Do not scale teacher
nodes further on this 40k set. Next 768: **more positions** at the teacher
that already won nodes (`go nodes 8000`), not another static dump and not
SF18 Elo 2000. King-relative still waits on eval H1.
