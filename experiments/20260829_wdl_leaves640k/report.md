# Honest 640k search leaves + path WDL — still a coin flip

Date: 2026-09-02. Follow-up to [320k leaves](../20260829_wdl_leaves320k/report.md)
after the 4096-game corpus. Candidate is `768×128` from `--init internal` on
static labels of **640 000 search leaves** (no game WDL) plus **363 091**
played-path FENs with a finished-game result,
`--target-mode wdl --result-weight 0.20 --residualize-extras --augment mirror`
(`nets/nnue_wdl_leaves640k.bin`, extras on). One UCI change: `EvalFile`.
`baseline.uci` unchanged. Result-weight was not raised.

## Data

Uniform sample of **640 000** `search_leaf` labeled with UCI `eval details`
(seed 20260814). Path FENs from finished games after 4096 self-play
(**363 091**, all with `1-0`/`0-1`/`1/2-1/2`). Mix: **1 003 091** rows.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814, `--init internal --augment mirror`.
Best epoch **2**. Clone gate **PASS**: C++ MAE **5.17** vs static (N=84762),
affine slope ~1.05.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_leaves640k | **12-181-7** | **0.512** | **+9 ± 15** | 388521 | 389814 |

Candidate score **0.488**. Interval includes 0. 0 overruns.
`promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5; no SPRT).
No SPRT.

## Decision

A 2× static mix after 4096 games still does not beat this tree. Scaling
`--label static` + path WDL (80k → 160k → 320k → 640k) stays a coin flip.
Do not raise `result-weight`. Do not SPRT. Do not grow 100M static leaves as
the Elo path. Next professor is NSCE search labels on leaves, WDL only on
path/root; king-bucket extras-off is a separate candidate with the same gate.
