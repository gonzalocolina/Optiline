# Roadmap y gates de aceptación

## Completado

| Gate / Fase | Criterio |
| --- | --- |
| A Corrección | Perft exacto; make/unmake estable |
| B Jugable | UCI + ID + alfa-beta + QS + TT |
| C Protocolo | hypothesis.md + tools smoke/ladder |
| Fase 3 | NMP, LMR, aspiration, futility, history/countermoves, Lazy SMP |
| Fase 4 | NNUE incremental int16, `UseNNUE` / `EvalFile`, distilación HCE |
| Fase 5 | Política de ordenación `UsePolicy` / `PolicyFile` |
| Fase 6 | Controlador `ΔR` + telemetría `TelemetryFile` |
| Fase 7 | Autojuego + fit `train/run_train_loop.sh` bajo movetime |
| Fase 8 | AVX2 NNUE, `-march=native`, LTO, prefetch TT, PGO opcional |

## Hipótesis (sigue abierta)

La política neuronal de presupuesto debe medirse con ablations a equal-time en la escalera Elo.

## Laboratorio experimental (activo)

El evaluador se fabrica y se juzga en el orden de [docs/eval_pipeline.md](eval_pipeline.md).
No se salta al árbol ni a una red más recargada.

Ver [docs/experiments.md](experiments.md) y `experiments/YYYYMMDD/`.

Comandos:

```bash
python3 tools/ablation_match.py --matrix --outdir experiments/$(date +%Y%m%d)
python3 tools/elo_ladder.py --outdir experiments/$(date +%Y%m%d)
python3 tools/sprt.py --cfg-b tools/configs/controller.uci
bash tools/run_experiment_day.sh
```
