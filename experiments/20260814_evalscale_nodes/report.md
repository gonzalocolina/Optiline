# Calibrated EvalScale / search-scale (frozen Stockfish references)

Date: 2026-08-14. Frozen identities: `experiments/frozen-targets/manifest.json`.

- NSCE 0.10 `build/nsce`
- Stockfish 18 ubuntu-x86-64-avx2 (`6b087694…`)
- Stockfish dev-20260810-5062aee5 (`f4451f72…`)
- Historical ladder PATH binary is Stockfish 17 (`4c22bce7…`), not SF18

`kat_nsce25k.bin` is not in this experiment. It already lost equal-node despite better MAE.

## Holdout affine fit

Data: `train/data/sf18_nodes25k.jsonl` holdout N=20157 (`sha256(fen)` group split).
Candidate: `nets/nnue_sf25k.bin`, extras off. Baseline: internal + extras.
Raw MAE: trained 109.4 vs baseline 140.9 (+31.4 cp). Same sign as the earlier 113.0 vs 143.6 gate.

| Fit (y from x) | origin scale | EvalScale | std_y / std_x | intercept |
| --- | ---: | ---: | ---: | ---: |
| baseline ← trained | 1.091 | **1091** | 1.519 | −3.1 cp |
| SF labels ← baseline | 0.511 | **511** | 1.175 | +19.3 cp |
| SF labels ← trained | 1.054 | 1054 | 1.784 | +24.2 cp |

The SF-teacher 768 is already on Stockfish search-cp (~1.05×). Frozen baseline eval is about **2×** those labels. Search constants were tuned to the larger baseline unit. Affine `EvalScale` can only multiply; intercepts are small.

## Equal node (`go nodes 25000`, N=200, seed 20260814)

Openings `openings_balanced.epd`, max plies 60, 0 overruns. Positive Elo is baseline stronger. Need challenger score clearly > 0.5.

| Candidate | W-D-L (baseline) | Score A | Elo A−B ±95% | cand. score | Path |
| --- | ---: | ---: | ---: | ---: | --- |
| frozen eval, `EvalScale=511` | 12-179-9 | 0.508 | **+5 ± 16** | 0.492 | [scale511](scale511/report.md) |
| `nnue_sf25k` `EvalScale=1091` | 23-169-8 | 0.538 | **+26 ± 19** | 0.462 | [sf25k_1091](sf25k_1091/report.md) |
| `nnue_sf25k` `EvalScale=1519` | 28-160-12 | 0.540 | **+28 ± 22** | 0.460 | [sf25k_1519](sf25k_1519/report.md) |
| `nnue_sf25k` unscaled (prior N=400) | 43-338-19 | 0.530 | +21 ± 13 | 0.470 | [nodes400](../20260814_sf25k_768_nodes400/report.md) |

Scaling the frozen baseline toward Stockfish units is a **coin flip**. Scaling the SF 768 onto baseline magnitude **still loses**, same sign as unscaled N=400. The equal-node hole is not a global affine scale mismatch.

**No SPRT. `baseline.uci` stays `EvalScale=1000`. Do not promote `nnue_sf25k.bin` at any of these scales.**

Pawn/threat features and hardware optimizations were not run.
