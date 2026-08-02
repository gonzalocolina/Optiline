# SPRT — SearchController vs frozen baseline (100 ms, max_plies=160, N=600)

- Date: 2026-08-02
- Engine: `build/nsce` (same binary both sides)
- Hypothesis: controller (`UseSearchController=true`) is stronger than frozen baseline at equal time
- H0: Elo(controller − baseline) ≤ −5
- H1: Elo(controller − baseline) ≥ +5
- α = β = 0.05 → bounds ≈ ±2.944
- Movetime: **100 ms** (`exploratory_short_tc=false`)
- Max games: **600** (300 color-reversed opening pairs), seed **7**
- Max plies: **160**
- Eval: both sides **`EvalFile=internal`** (same Hash/Threads/NNUE/policy); only `UseSearchController` differs

| Side | Config |
| --- | --- |
| A baseline | `tools/configs/baseline.uci` |
| B candidate | `tools/configs/controller.uci` |

## Result

| Metric | Value |
| --- | --- |
| Decision | **inconclusive** |
| W–D–L (controller) | **51–496–53** |
| Games / pairs | **600** / **300** |
| Score (controller) | 0.4983 |
| Approx. Elo(B−A) | ≈ **−1.2** |
| Final LLR | **−0.331** (inside [−2.944, +2.944]) |
| LLR range observed | ≈ [−2.527, +0.821] |

### Terminations

| Kind | Count |
| --- | --- |
| draw (rules) | 298 |
| max_plies | 198 |
| consensus_eval | 89 |
| checkmate | 15 |

## Interpretation

- Configs isolate the controller: frozen internal NNUE on both sides; trained net not used.
- Raising `max_plies` from 60 → 160 cut truncation vs the prior 100 ms SPRT (198/600 ≈ 33% vs ~87% max-plies), with more rule draws and adjudications.
- At ±5 Elo and ~83% draws, N=600 still does not decide. LLR never crossed either bound; point estimate is noise-compatible with equality.
- **Hypothesis remains open / not confirmed:** no evidence that `UseSearchController` is ≥ +5 Elo stronger (nor ≤ −5 Elo weaker) under this protocol.

Compared with `experiments/20260802_sprt_controller_100ms/` (N=400, max_plies=60, WDL 9–384–7, LLR +1.42): longer games flipped the tiny point estimate toward equality and kept the SPRT inconclusive.

## Artifacts

- `sprt_controller.json` — full history + LLR path
- `manifest.json` — pinned binary/configs/openings
- `sprt.log` / `sprt_resume2.log` — console logs (run resumed once after an early interrupt)
- `report.md` — this file

## Tooling note

`tools/sprt.py` now supports `--resume` and snapshots after every game so interrupted runs can continue without losing odd games.
