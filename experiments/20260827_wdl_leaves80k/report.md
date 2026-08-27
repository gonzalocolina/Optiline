# Honest 80k search leaves + path WDL — still a coin flip

Date: 2026-08-27. Follow-up to [wdl leaves](../20260814_wdl_leaves/report.md) after
fixing leaf-label provenance. Candidate is `768×128` from `--init internal` on
static labels of **80 000 search leaves** (no game WDL) plus **21 705 played-path**
FENs with a finished-game result, `--target-mode wdl --result-weight 0.20
--residualize-extras --augment mirror` (`nets/nnue_wdl_leaves80k.bin`, extras on).
One UCI change: `EvalFile`. `baseline.uci` unchanged.

The 20k run stamped every QS/static leaf with the game result. That was wrong.
`stamp_leaf` now copies WDL only onto the search root (`label_kind=path`).

## Data

Salvaged `train/data/leaves_with_results.jsonl`: **4 613 450** records,
**2 336** path with result, rest `search_leaf` unlabeled.
Uniform sample of **80 000** `search_leaf` labeled with UCI `eval details`.
Path FENs from 180 finished games in `selfplay_colors.jsonl` labeled the same way
(**21 705**, all with `1-0`/`0-1`/`1/2-1/2`). Mix: 101 705 rows.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch 2. Clone gate **PASS**: C++ MAE **3.09** vs static (N=9705), affine
slope 1.00. Closer to the arbiter than the poisoned 20k net (MAE 12.9).

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_leaves80k | **12-175-13** | **0.497** | **−2 ± 17** | 391036 | 387415 |

Candidate score **0.502**. Interval includes 0. 0 overruns.
`promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5; no SPRT).
No SPRT.

## Decision

Honest WDL mix at 80k leaves does not beat this tree. Do not raise
`result-weight`. Do not KAT. Next is more games/leaves (streaming datagen),
not another 768 architecture.
