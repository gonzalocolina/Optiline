# Ablation report — 20260802_search_ablation_smoke

- Engine: `build/nsce`
- Games/match: 8
- Color-reversed opening pairs: 4
- Movetime: 80 ms
- Date: 2026-08-02

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline vs no_tt | 2-6-0 | 0.625 | +89 ± 131 | 1027018 | 1082903 | 0+0 |
| baseline vs no_see | 1-7-0 | 0.562 | +44 ± 106 | 925091 | 911826 | 0+0 |
| baseline vs no_lmr | 2-6-0 | 0.625 | +89 ± 131 | 820595 | 662199 | 0+0 |
| baseline vs no_nullmove | 2-6-0 | 0.625 | +89 ± 131 | 1011467 | 883578 | 0+0 |
| baseline vs no_futility | 0-7-1 | 0.438 | -44 ± 106 | 992362 | 1035339 | 0+0 |
| baseline vs no_lmp | 0-7-1 | 0.438 | -44 ± 106 | 1051087 | 1299907 | 0+0 |
| baseline vs no_razoring | 1-7-0 | 0.562 | +44 ± 106 | 997510 | 904640 | 0+0 |
| baseline vs no_rfp | 0-8-0 | 0.500 | +0 ± 73 | 1040901 | 1049772 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

