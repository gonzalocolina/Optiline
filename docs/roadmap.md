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

La política neuronal de presupuesto debe medirse con ablations a equal-time en la escalera Elo. Los componentes están cableados; el entrenamiento a escala y SPRT vs Stockfish son el trabajo experimental continuo.
