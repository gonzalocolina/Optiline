# Ablation report — scale511

- Engine: `build/nsce`
- Games/match: 200
- Color-reversed opening pairs: 100
- Movetime: 100 ms
- Date: 2026-08-14

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline vs evalscale511 | 12-179-9 | 0.507 | +5 ± 16 | 393245 | 414815 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

