# Honest 320k search leaves + path WDL — still a coin flip

Date: 2026-08-29. Follow-up to [160k leaves](../20260827_wdl_leaves160k/report.md)
after the 1024→2048 datagen increment
([datagen 2048](../20260827_datagen2048/report.md)). Candidate is `768×128`
from `--init internal` on static labels of **320 000 search leaves** (no game
WDL) plus **167 991 played-path** FENs with a finished-game result,
`--target-mode wdl --result-weight 0.20 --residualize-extras --augment mirror`
(`nets/nnue_wdl_leaves320k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged. Result-weight was not raised.

## Data

Uniform sample of **320 000** `search_leaf` labeled with UCI `eval details`
(seed 20260814). Path FENs from 1475 finished games (**167 991**, all with
`1-0`/`0-1`/`1/2-1/2`). Mix: 487 991 rows.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch 8. Clone gate **PASS**: C++ MAE **6.90** vs static (N=40659), affine
slope ~1.02.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_leaves320k | **10-181-9** | **0.502** | **+2 ± 15** | 393091 | 392298 |

Candidate score **0.498**. Interval includes 0. 0 overruns.
`promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5; no SPRT).
No SPRT.

## Decision

A 2× honest mix after 2048 games still does not beat this tree. Do not raise
`result-weight`. Do not KAT. Next is more games/leaves (streaming datagen),
not another 768 architecture and not an equal-time SPRT.
