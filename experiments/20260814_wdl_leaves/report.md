# Leaf labels with game results — still not a companion

Date: 2026-08-14. Follow-up to [wdl colors](../20260814_wdl_colors/report.md).
Candidate is `768×128` from `--init internal` on static labels of **search
leaves** stamped with a finished self-play result, `--target-mode wdl
--result-weight 0.20 --residualize-extras --augment mirror`
(`nets/nnue_wdl_leaves.bin`, extras on). One UCI change: `EvalFile`.

Path FENs from the same 256 games were coin flips. This run labels the positions
the tree actually scores.

## Data

180 finished games from `train/data/selfplay_colors.jsonl` (skip `max_plies`).
Three path roots per game (opening / mid / late) × `go nodes 25000` → **540**
searches, **4 613 450** unique leaves (`q_stand_pat`, `static`,
`in_check_static`), each carrying that game’s `result`.

Uniform sample of **20 000** labeled with UCI `eval details`. All 20 000 have a
real result (9414 × 1-0, 7134 × 0-1, 3452 × 1/2-1/2) from **117** of the 180
games. Sites in the sample: 15 669 stand-pat, 4331 static.

## Train

20 000 unique FENs, 117 groups, holdout 2145. Adam 32 ep, lr `4e-4`, seed
20260814. Best epoch 11. Net ≠ clone
(`sha256 8c5689f0…` vs clone export `3e544b86…`).

| Epoch | Val MAE vs WDL+result target | Val RMSE |
| ---: | ---: | ---: |
| 0 | 138.8 | 158.9 |
| 11 (best) | 137.4 | 154.4 |
| 32 | 138.5 | 154.9 |

The objective barely moves. Same pattern as the path-FEN WDL nets.

## C++ integers vs static teacher

Holdout N=1831, extras on, runtime composite delta 0.

| Engine | MAE vs static labels | Sign |
| --- | ---: | ---: |
| internal + extras | **0.00** | 1.00 |
| `nnue_wdl_leaves.bin` + extras | **12.9** | 0.95 |

Clone gate **PASS** (ceiling 15). Affine vs baseline slope 1.04. Further from
the arbiter than the 256-path net (MAE 8.1), closer than the 64-game net
(MAE 27.5). Not wreckage. MAE is not promotion.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both, one UCI change.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_leaves | **11-172-17** | **0.485** | **−10 ± 18** | 388512 | 386758 |

Candidate score **0.515**. First WDL mix whose point estimate is on the
candidate’s side. The interval still includes 0. 0 overruns.
`promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5; no SPRT).
`baseline.uci` unchanged. No SPRT.

## Decision

Leaves with a finished-game result, 20k of 4.6M, still do not beat this tree.
Do not SPRT a +10 ± 18. Do not KAT. Do not retune search.

Next is not a new architecture: the dump is already on disk. Label a **larger
uniform sample** of those same leaves (same 768 + extras, same WDL mix) before
changing `result-weight` or collecting more games.
