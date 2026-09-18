# EvalScale 926 on the promoted 768

Date: 2026-09-09. Pipeline step 9: one search-group change. Candidate
`tools/configs/evalscale_926.uci` keeps `EvalFile=nets/nnue_search_leaves40k_rw0.bin`
and extras on. Hypothesis: holdout affine of that net onto frozen internal
static is 0.926
([validation](../20260903_search_leaves40k_rw0/validation.json)); RFP / razor /
futility constants were written for the internal unit, so `EvalScale=926` is the
calibration.

## Equal node (`go nodes 25000`)

N=200, seed 20260814. Auto `report.md` from `ablation_match.py` prints the
default movetime line; the match was **nodes** (`nodes_per_move=25000`).

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| EvalScale 1000 vs 926 | **10-176-14** | **0.490** | **−7 ± 17** | 388148 | 389607 |

Candidate score **0.515**. Interval includes 0. 0 overruns. `equal_node_clearly_winning`:
**FAIL**. No SPRT. Do not promote. `baseline.uci` stays `EvalScale=1000`.

## Decision

An 8% affine nudge does not change this tree. Same lesson as `EvalScale=511` on
the old internal (coin flip) and 1091/1519 on the SF 768 (still lost). Do not
fish other permille values. Next one-change on this eval is policy or the LMR
controller, fitted for **this** net, not a replay of the internal-era weights.
