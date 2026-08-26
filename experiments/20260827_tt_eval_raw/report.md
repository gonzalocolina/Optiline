# Ablation report — 20260827_tt_eval_raw

- Engine: `build/nsce-p0-before`
- Games/match: 200
- Color-reversed opening pairs: 100
- Movetime: 100 ms
- Date: 2026-08-27

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| A vs B | 13-177-10 | 0.507 | +5 ± 17 | 389603 | 391019 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

