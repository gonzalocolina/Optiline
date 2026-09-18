# LMR controller re-fit on the promoted 768

Date: 2026-09-09. One controller-group change vs `baseline.uci`:
`UseSearchController=true` + `ControllerFile=nets/controller_rw0.bin`.
`EvalFile` stays `nets/nnue_search_leaves40k_rw0.bin`. Telemetry collected with
that eval, controller **off** (`train/collect_search_telemetry.py --depth 8
--limit 64`). Fit: 267 333 LMR events, ridge MAE 16.2, `w_cut=-9` dominates
(`w_improving=-6`, `bias=0`, `w_see=0`). Clamp stays `[-1, +2]`.

## Equal node (`go nodes 25000`)

N=200, seed 20260814. Auto `report.md` prints the default movetime line; the
match was **nodes** (`nodes_per_move=25000`).

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| classical LMR vs controller_rw0 | **9-182-9** | **0.500** | **+0 ± 15** | 392548 | 392432 |

Candidate score **0.500**. Interval includes 0. 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.
`UseSearchController` stays false.

## Decision

Re-fitting LMR on this eval does not change the tree (same sign as the
internal-era fit, which was slightly negative at equal time). Do not relax the
clamp. Do not mix policy into this file. Next one-change is policy fitted for
**this** 768, not `tools/configs/policy.uci` (`EvalFile=internal`).
