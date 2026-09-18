# Honest 160k search leaves + path WDL — still a coin flip

Date: 2026-08-27. Follow-up to [80k leaves](../20260827_wdl_leaves80k/report.md)
after the 512→1024 datagen increment
([datagen 1024](../20260827_datagen1024/report.md)). Candidate is `768×128`
from `--init internal` on static labels of **160 000 search leaves** (no game
WDL) plus **84 043 played-path** FENs with a finished-game result,
`--target-mode wdl --result-weight 0.20 --residualize-extras --augment mirror`
(`nets/nnue_wdl_leaves160k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged. Result-weight was not raised.

## Data

`train/data/leaves_with_results.jsonl` after 1024 self-play games:
`collect_leaves --append` added **4 886 429** unique leaves on top of the 512
increment. Uniform sample of **160 000** `search_leaf` labeled with UCI
`eval details` (seed 20260814). Path FENs from 718 finished games
(**84 043**, all with `1-0`/`0-1`/`1/2-1/2`). Mix: 244 043 rows.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch 2. Clone gate **PASS**: C++ MAE **3.85** vs static (N=21046), affine
slope 1.02.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_leaves160k | **17-168-15** | **0.505** | **+3 ± 19** | 391730 | 387074 |

Candidate score **0.495**. Interval includes 0. 0 overruns.
`promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5; no SPRT).
No SPRT.

## Decision

A larger honest WDL mix still does not beat this tree. Do not raise
`result-weight`. Do not KAT. Next is more games/leaves (streaming datagen),
not another 768 architecture and not an equal-time SPRT.
