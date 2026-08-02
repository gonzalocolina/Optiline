# Ablation report — 20260802_nnue_confirmation

- Engine: `build/nsce`
- Games/match: 20
- Color-reversed opening pairs: 10
- Movetime: 100 ms
- Date: 2026-08-02

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| frozen_hce vs trained_nnue | 0-19-1 | 0.475 | -17 ± 46 | 960774 | 864019 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

