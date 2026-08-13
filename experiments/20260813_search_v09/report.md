# Ablation report — 20260813_search_v09

- Engine: `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce`
- Games/match: 40
- Color-reversed opening pairs: 20
- Movetime: 100 ms
- Date: 2026-08-13

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| nsce09 vs nsce08 | 2-36-2 | 0.500 | +0 ± 37 | 1218886 | 1468783 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

