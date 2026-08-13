# extras() off vs frozen 768 baseline (SPRT)

Date: 2026-08-13. Candidate: `EvalFile=internal` with `UseExtras=false`.
Baseline keeps HCE `extras()` on the distilled 768×128 net. King-bucket nets
already skip extras; this tests the frozen 768 path only.

## SPRT

- `extras_off.uci` vs `baseline.uci`, 100 ms, min 40 / max 200, seed 20260813

| Decision | W-D-L (extras_off) | Games | LLR |
| --- | ---: | ---: | ---: |
| **accept_H0_baseline_not_worse** | 3-87-36 | 126 | −2.97 |

Score 0.369. `extras()` is **load-bearing** on the HCE-distilled 768 net (unlike KAT,
where extras fought the net). Keep `UseExtras=true` on the frozen baseline.
