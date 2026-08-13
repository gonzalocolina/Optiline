# KAT vs internal after 2× timed nodes (SPRT)

Date: 2026-08-13. Same `NSCEKAT1` 1M×16 net as [kat_e16_sprt](../20260813_kat_e16_sprt/report.md).
Engine includes KAT madd inference and latched time-up (~2× nodes at 100 ms).

## SPRT

- `kat.uci` vs `baseline.uci`, 100 ms, min 40 / max 200, seed 20260813
- Openings: `openings_balanced.epd`

| Decision | W-D-L (KAT) | Games | LLR |
| --- | ---: | ---: | ---: |
| **accept_H0_baseline_not_worse** | 13-51-52 | 116 | −3.04 |

Score 0.332 vs 0.403 on the pre-speedup 8-epoch H0. Faster KAT inference did **not**
flip equal-time. The bushier tree still loses when both sides get ~2× nodes.
Do not replace `EvalFile=internal`. Do not replay this net at 100 ms.
