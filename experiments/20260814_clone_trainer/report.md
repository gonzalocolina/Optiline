# Clone trainer stays on the teacher once color-flip is off

Date: 2026-08-14. Follow-up to [clone nodes](../20260814_clone_nodes/report.md).
Same 20 000 static leaf labels, `--init internal`, `--residualize-extras`,
`--target-mode cp`, Adam lr `4e-4`.

## Cause

The 768 net is white-absolute with ReLU and all-positive `w1`. Color-flip plus
`-y` is a symmetry of an odd linear map, not of this net.

On 2048 clone-train positions, epoch-0 QAT MAE vs the residualized static
labels:

| Variant | MAE (cp) | Sign accuracy |
| --- | ---: | ---: |
| identity | **0.04** | 0.989 |
| horizontal mirror | 0.41 | 0.977 |
| color-flip | **290** | **0.00** |
| color-flip + mirror | **290** | **0.00** |

Color-flip predictions averaged +206 cp against a −84 target. About half the
hidden units sit below ReLU on the original position and above it after the
flip (`acc0 + acc2` mean abs 0.46, not 0).

A second trainer bug: epoch 0 was never scored, so the first wrecked epoch
became “best” and was exported.

## Fix

- `--augment none|mirror|full` (default `mirror`). Clone script uses `none`.
- Score epoch 0 and keep it when later epochs are worse.
- `full` remains available only as a diagnostic.

## Same 16-epoch recipe as the MAE 35 failure

| Augment | Epoch 0 | Epoch 1 | Epoch 16 | Best epoch | Exported C++ MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| `none` | 0.030 | **0.062** | 0.138 | 0 | **0.00** (N=1987) |
| `mirror` | 0.030 | 0.185 | 0.331 | 0 | **0.00** (same sha256) |
| `full` (4 ep) | 0.030 | **33.7** | 63.2 at ep 4 | 0 | 0.00 (restored ep 0) |

`none` / `mirror` stay on the teacher (last-epoch MAE under 0.4 cp). `full`
reproduces the old walk-off. Because epoch 0 is now eligible, a `full` run
still exports the clone; that is a safety net, not a reason to train with
color-flip.

Exported `nnue_clone_stay.bin` sha256 matches `nnue_clone_export.bin`.
`validate_nnue.py --gate clone`: **PASS**. No new equal-node match (identical
binary). `baseline.uci` unchanged.

## Decision

The optimizer can stay on a teacher it already matches. Step 1 of
[eval_pipeline.md](../../docs/eval_pipeline.md) is unblocked for a trained 768.
Next is data with game results (WDL mix), still 768 + extras, then equal-node
N≥200 clearly above 0.5. Not KAT, not search retune, not color-flip.
