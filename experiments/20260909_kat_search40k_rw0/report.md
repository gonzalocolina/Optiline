# King-relative `--no-threats` on the promoted 40k mix

Date: 2026-09-09. Pipeline step 8: HalfKA-hm 32, hidden 128, 12-threat residual
**off**, extras **off**, same `train/data/nsce_search_mix_40k.jsonl` and
result-weight 0 as `nets/nnue_search_leaves40k_rw0.bin`. Candidate
`nets/kat_search_leaves40k_rw0.bin`. One eval-group change vs promoted baseline:
`EvalFile` + `UseExtras=false` (`EvalScale` stays 1000).

## Train

`train/train_kat.py --no-threats`, Adam 32 ep, lr `4e-4`, seed 20260814,
`--target-mode wdl --search-wdl-scale 400 --teacher-wdl-scale 400`. No internal
init (KAT has none). Threat weights zeroed from the first step. 79 999 unique
rows. Best export is lowest val **RMSE** (epoch ~10–32); epoch 1 had the best
MAE (**195** cp, sign 0.74) and later MAE rose to **222**. Float val MAE vs
search/WDL **222** (sign 0.71). Deployed C++ MAE vs frozen static **138**
(N=6737, extras off on the candidate). Affine origin vs those static labels
**0.31**. Threats flag in metrics: false.

## Equal node (`go nodes 25000`)

N=200, seed 20260814. Auto `report.md` from `ablation_match.py` prints the
default movetime line; the match was **nodes** (`nodes_per_move=25000` in
`ablation_summary.json` / `manifest.json`).

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| promoted 768 vs kat40k_rw0 | **111-87-2** | **0.773** | **+212 ± 36** | 376968 | 376332 |

Candidate score **0.228**. Interval excludes 0. 0 overruns. Time/game ~578 ms vs
539 ms (not a speed story). `equal_node_clearly_winning`: **FAIL**. No SPRT. Do
not promote.

## Decision

This tree does not recognize a from-scratch king-relative net on the same
labels. Do not add the 12-threat residual, hidden 256, or policy on this loser.
Keep `nets/nnue_search_leaves40k_rw0.bin`. Next legal lever is grouped
search-margin / `EvalScale` retune for **that** net (`promotion_gate --stage
search`), not another KAT.
