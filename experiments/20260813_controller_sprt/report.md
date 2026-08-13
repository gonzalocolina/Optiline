# SPRT: fitted LMR controller vs frozen baseline

Date: 2026-08-13. Candidate: `UseSearchController=true` with `NSCECTL2` from
self-search LMR telemetry. Baseline: `tools/configs/baseline.uci` (`EvalFile=internal`,
controller off). One candidate; extras/KAT not mixed in.

## Fit

- Telemetry: 246410 LMR events (`train/collect_search_telemetry.py --depth 8 --limit 64`)
- Features: depth, index, eval_gap, quiet, policy, hist, improving, cut_node, SEE sign
- Export: `nets/controller_fitted.bin` (`NSCECTL2`, 10 × int32)
- Ridge MAE on raw residual: 14.4
- Weights: `w_depth=-4 w_index=-1 w_eval_gap=1 w_quiet=2 w_policy=-1 bias=0 w_hist=-4 w_improving=-4 w_cut=-11 w_see=0`
- Runtime clamp still **[-1, +2]**

## SPRT

- Openings: `tools/openings_balanced.epd`, seed 20260813
- Movetime 100 ms, max plies 80, Hash 16, Threads 1
- `--elo0 -5 --elo1 5`, α=β=0.05, **min 40 games**, max 200
- Pair-level pentanomial LLR (variance floor 0.04; a prior 2-game H1 was invalid)

| Decision | W-D-L | Pentanomial | LLR | Bounds |
| --- | ---: | --- | ---: | --- |
| inconclusive | 23-143-34 | see `sprt_controller.json` | −0.99 | [−2.94, +2.94] |

The point estimate is slightly negative. Do **not** set `UseSearchController` on
the frozen baseline. Re-fit after more research/cutoff labels, or relax the clamp
only if a later SPRT accepts H1 and Elo/nodo rises at equal time.

## Not done

Equal-node nps comparison of controller on vs off. Not required to refuse promotion.
