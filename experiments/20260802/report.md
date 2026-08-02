# Ablation report — 20260802

- Engine: `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce`
- Games/match: 6
- Movetime: 50 ms
- Date: 2026-08-02

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline vs controller | 1-5-0 | 0.583 | +58 ± 282 | 270308 | 281896 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.

