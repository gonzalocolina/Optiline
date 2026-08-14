# Self-play WDL mix — equal-node coin flip

Date: 2026-08-14. Step 5 of [eval_pipeline.md](../../docs/eval_pipeline.md).
Candidate is `768×128` trained from `--init internal` on static labels of
self-play game paths, `--target-mode wdl --result-weight 0.20
--residualize-extras --augment mirror` (`nets/nnue_wdl.bin`, extras on).
One UCI change: `EvalFile`.

## Data

64 games, 100 ms, `--max-plies 200`, `openings_balanced.epd`, frozen baseline.

A `max_plies` cutoff is no longer written as `1/2-1/2`.

| Termination | Games | PGN |
| --- | ---: | --- |
| checkmate | 41 | 14 × 1-0, 27 × 0-1 |
| draw (rule) | 9 | 1/2-1/2 |
| max_plies (no result) | 14 | omitted |

Mean 137 plies. **8829** path positions labeled with UCI `eval details`;
**6015** carry a real result. Openings were played once, so the decisive sample
is color-imbalanced.

Mixing those games with the 20k clone leaves made validation clone-dominated:
best epoch 0, exported sha256 identical to the clone. The candidate below is
**games only**.

## Train (games only)

8467 unique FENs, 64 groups, holdout 408. Adam 32 ep, lr `4e-4`, seed 20260814.

| Epoch | Val MAE vs WDL+result target |
| ---: | ---: |
| 0 | 115.6 |
| 30 (best) | 114.1 |
| 32 | 114.2 |

The objective barely moves. Exported net ≠ clone.

## C++ integers vs static teacher

Holdout N=744, extras on, runtime `eval` vs `eval details` delta 0.

| Engine | MAE vs static labels | Sign |
| --- | ---: | ---: |
| internal + extras | **0.00** | 1.00 |
| `nnue_wdl.bin` + extras | **27.5** | 0.96 |

Clone gate **FAIL** (ceiling 15). Not wreckage. Affine vs baseline slope 1.11.
MAE is not promotion.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, `openings_balanced.epd`, extras on both, one UCI change.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl | **14-172-14** | **0.500** | **+0 ± 18** | 393163 | 394344 |

0 overruns. `promotion_gate.py --stage eval`: **FAIL** (not clearly above 0.5;
no equal-time SPRT). `baseline.uci` unchanged. No SPRT.

## Decision

64 games of result mix are not a new companion. The tree still sees the frozen
arbiter (coin flip, almost the same nodes). Next is more finished games with
both colors, still 768 + extras, `--augment mirror`. Not KAT, not search retune,
not color-flip, not raising `result-weight` to force a fit.
