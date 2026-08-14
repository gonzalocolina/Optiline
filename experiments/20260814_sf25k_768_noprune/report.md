# Ablation report — 20260814_sf25k_768_noprune

- Engine: `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce`
- Games/match: 40
- Color-reversed opening pairs: 20
- Movetime: 100 ms
- Date: 2026-08-14

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_noprune vs nnue_sf25k_noprune | 3-36-1 | 0.525 | +17 ± 37 | 436637 | 458397 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

