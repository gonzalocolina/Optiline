# NSCE — Neural Search Chess Engine

Motor de ajedrez UCI en C++20. Hipótesis: una política neuronal de presupuesto de búsqueda puede ganar Elo a igual CPU/tiempo frente a Stockfish.

## Estado actual (v0.10)

- Movegen legal pin-aware (doble jaque, evasiones y en-passant) validado con perft
- PVS/alpha-beta con IIR, ProbCut, NMP verificado, extensiones singulares dobles,
  continuation 1/2/4/6, capture/correction history y pick-next
- QS fail-soft, SEE de jugadas quietas y eval residual (movilidad, columnas, outposts)
- Telemetría `NSCE_STATS`, flags de ablación y tablas de ataques magic/PEXT
- NNUE `768x128x1` + residual clásico (peones pasados, pareja de alfiles, estructura)
- Runtime HalfKP (`NSCEHFKP`) y KAT (`NSCEKAT1`: HalfKA-hm 32 + residual táctico)
- **Laboratorio:** aperturas balanceadas, SPRT pentanomial, ablations
- Optimización: AVX2, LTO, `-march=native`, pool SMP persistente entre `go`

## Build

```bash
export PATH="$HOME/.local/bin:$PATH"
cmake -G "Unix Makefiles" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
cmake --build build -j"$(nproc)"
```

Opciones CMake: `NSCE_NATIVE`, `NSCE_LTO`, `NSCE_AVX2`, `NSCE_SANITIZE`,
`NSCE_TSAN`, `NSCE_STATS`, `NSCE_PGO_GENERATE`, `NSCE_PGO_USE`.

## Uso

```bash
./build/nsce
# UCI options: Hash, Threads, UseNNUE, UsePolicy, UseSearchController,
# EvalFile, PolicyFile, ControllerFile, TelemetryFile,
# UseTT, UseSEE, UseLMR, UseNullMove, UseFutility, UseLMP, UseRazoring, UseRFP, UseProbCut
```

```bash
ctest --test-dir build --output-on-failure
./build/nsce_bench 10 1 1
python3 tools/smoke_match.py --games 2
bash train/run_train_loop.sh
# Pipeline NNUE / HalfKP / KAT: train/README.md
# Telemetría y scorecards: docs/measurement.md
```

## Laboratorio

```bash
bash tools/run_experiment_day.sh experiments/$(date +%Y%m%d)
# o por piezas:
python3 tools/generate_openings.py --positions 256 --output tools/openings_balanced.epd
python3 tools/ablation_match.py --search-matrix --openings tools/openings_balanced.epd \
  --games 40 --seed 1 --outdir experiments/$(date +%Y%m%d)_search
python3 tools/sprt.py --cfg-b tools/configs/trained_nnue.uci \
  --openings tools/openings_balanced.epd --max-games 200 --seed 1
bash tools/profile_engine.sh
```

Los runners usan aperturas emparejadas con colores invertidos, SPRT pentanomial
por pares y escriben un `manifest.json` reproducible. Baseline y protocolo:
[docs/experiments.md](docs/experiments.md). Medición de arquitectura:
[docs/measurement.md](docs/measurement.md). Conocimiento acumulado del laboratorio:
[docs/knowledge.md](docs/knowledge.md).

## Licencia

MIT. No incorporar código GPL (p. ej. Stockfish) en este árbol.
