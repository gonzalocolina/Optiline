# Ablation report — 20260802_search_ablation

- Engine: `/home/gonzalo/Escritorio/Codigo/Optiline/build/nsce`
- Games/match: 40
- Color-reversed opening pairs: 20
- Movetime: 100 ms
- Date: 2026-08-02

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline vs no_tt | 4-36-0 | 0.550 | +35 ± 37 | 1328599 | 1476440 | 0+0 |
| baseline vs no_see | 2-35-3 | 0.487 | -9 ± 41 | 1286373 | 1301857 | 0+0 |
| baseline vs no_lmr | 4-35-1 | 0.537 | +26 ± 40 | 1349127 | 1164292 | 0+0 |
| baseline vs no_nullmove | 4-33-3 | 0.512 | +9 ± 47 | 1301448 | 1128082 | 0+0 |
| baseline vs no_futility | 4-36-0 | 0.550 | +35 ± 37 | 1329915 | 1368823 | 0+0 |
| baseline vs no_lmp | 0-37-3 | 0.463 | -26 ± 33 | 1289223 | 1653785 | 0+0 |
| baseline vs no_razoring | 1-37-2 | 0.487 | -9 ± 33 | 1297352 | 1312995 | 0+0 |
| baseline vs no_rfp | 2-38-0 | 0.525 | +17 ± 29 | 1327775 | 1318615 | 0+0 |

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- For hypothesis, Policy/Controller should raise challenger strength (Elo A−B ≤ 0) and/or improve Elo/nodo.
- All matrix comparisons are pre-registered and always run; no data-dependent combo gate.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.

