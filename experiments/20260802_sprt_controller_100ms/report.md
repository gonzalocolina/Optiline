# SPRT — SearchController vs frozen baseline (100 ms)

- Date: 2026-08-02
- Engine: `build/nsce`
- Hypothesis: controller (`UseSearchController=true`) is stronger than frozen baseline at equal time
- H0: Elo(controller − baseline) ≤ −5
- H1: Elo(controller − baseline) ≥ +5
- α = β = 0.05 → bounds ≈ ±2.944
- Movetime: **100 ms** (`exploratory_short_tc=false`)
- Max games: **400** (200 color-reversed opening pairs), seed 42
- Max plies: 60
- Eval: both sides **`EvalFile=internal`** (frozen HCE-distilled NNUE; trained net not used)

| Side | Config |
| --- | --- |
| A baseline | `tools/configs/baseline.uci` |
| B candidate | `tools/configs/controller.uci` |

## Result

| Metric | Value |
| --- | --- |
| Decision | **inconclusive** |
| W–D–L (controller) | **9–384–7** |
| Score (controller) | 0.5025 |
| Approx. Elo(B−A) | ≈ +1.7 |
| Final LLR | +1.416 (inside [−2.944, +2.944]) |
| Opening pairs | 200 |

### Terminations

| Kind | Count |
| --- | --- |
| max_plies | 347 |
| draw (rules) | 37 |
| consensus_eval | 11 |
| checkmate | 5 |

## Interpretation

- Configs isolate the controller: same Hash/Threads/NNUE/`EvalFile=internal`; only `UseSearchController` differs.
- At ±5 Elo and this draw rate (~96%), N=400 is still under-powered; LLR never crossed either bound.
- Point estimate slightly favors the controller but is noise-compatible with equality.
- Most games hit `max_plies=60` without mate/adjudication → low information per game. For a decisive SPRT, raise `max_plies` and/or soften adjudication, or widen the Elo gap / increase N further.

## Artifacts

- `sprt_controller.json` — full game history + LLR path
- `manifest.json` — pinned binary/configs/openings
- `sprt.log` — console log
