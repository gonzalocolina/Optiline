# Ablation report — 20260829_nps_movepicker

- Engine A: `build/nsce` (frozen search)
- Engine B: `build-nps/nsce` (staged MovePicker + SEE reuse)
- Same `tools/configs/baseline.uci`
- Games/match: 200
- Color-reversed opening pairs: 100
- Equal-node: 25k, seed 20260814, `openings_balanced.epd`
- Date: 2026-08-29

| Match | W-D-L (A) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B | overruns |
| --- | --- | --- | --- | --- | --- | --- |
| baseline vs nps | 20-170-10 | 0.525 | +17 ± 19 | 384276 | 395650 | 0+0 |

Candidate score **0.475**. `promotion_gate --stage search` FAIL (not clearly above 0.5). No equal-time SPRT. Source reverted to the frozen search; `build-nps/nsce` kept as the measured binary. Bench had higher nps (depth-12 ~865k→993k) but the tree lost at equal nodes.

## Interpretation

- Positive Elo A−B ⇒ baseline stronger than challenger.
- Evaluation adjudication requires alternating-engine consensus; max-ply positions are draws.


