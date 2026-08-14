# Clone the frozen arbiter — export pipe passes, SGD does not

Date: 2026-08-14. Step 1 of [eval_pipeline.md](../../docs/eval_pipeline.md).
Candidate is the frozen HCE 768 re-exported through `train_nnue.py --init internal
--epochs 0 --residualize-extras` (`nets/nnue_clone_export.bin`, extras on).

## Labels

- 64 book positions × `go nodes 25000` with `LeafTelemetryFile` → **832 841** unique
  leaves (`q_stand_pat`, `static`, `in_check_static`).
- Uniform sample of **20 000** labeled with UCI `eval details` (deployed static
  eval, not `go nodes`). Holdout N=1987. Baseline C++ vs those notes: **MAE 0**.

## C++ clone gate

| Net | How | Engine MAE vs static labels | Gate |
| --- | --- | ---: | --- |
| `nnue_clone_export.bin` | quantize internal, 0 epochs | **0.00** (N=1987) | PASS |
| `nnue_clone.bin` (trained) | Adam 16 ep, lr 4e-4, 20k leaves | 35.4 | FAIL |
| prefix 2k, 50 ep, lr 3e-3 | first dump slice | 15.2 | FAIL (15.0 ceiling) |

Runtime `eval` and `eval details` agree (max abs delta 0). Affine clone vs
baseline is slope 1.00. The train → export → C++ **load** path can copy the
arbiter. SGD on the arbiter’s own notes **walks off it** from epoch 1
(validation MAE 36.8 → 72.8). Do not treat a trained 768 as a clone until that
is fixed. The equal-node candidate is the export net.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, `openings_balanced.epd`, extras on both, one UCI change
(`EvalFile`).

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | --- | ---: | ---: | ---: | ---: |
| baseline vs clone | **8-184-8** | **0.500** | **+0 ± 14** | 386603 | 386603 |

Identical node counts. 0 overruns. `promotion_gate.py --stage clone`: **PASS**.
The quantized export is the same companion as `EvalFile=internal`.

No 100 ms SPRT (not a strength claim). `baseline.uci` unchanged.

## Decision

Step 1 **holds for the export pipe**. A richer net is still illegal. The SGD
walk-off was color-flip on a ReLU net; that is fixed in
[clone trainer](../20260814_clone_trainer/report.md). Next is data with game
results on this proven path, not KAT and not search.
