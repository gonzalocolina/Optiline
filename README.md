# NSCE — Neural Search Chess Engine

Motor de ajedrez UCI en C++20. Hipótesis: una política neuronal de presupuesto de búsqueda puede ganar Elo a igual CPU/tiempo frente a Stockfish.

## Estado actual (v0.8 + lab)

- Núcleo bitboard + perft + UCI (`status` para adjudicar)
- Búsqueda competitiva + NNUE/política/controlador
- **Laboratorio:** baseline congelado, ablations, escalera Elo, SPRT, autojuego con resultados, destilación
- Optimización: AVX2, LTO, `-march=native`, bench de latencia NNUE

## Build

```bash
export PATH="$HOME/.local/bin:$PATH"
cmake -G "Unix Makefiles" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
cmake --build build -j"$(nproc)"
```

Opciones CMake: `NSCE_NATIVE`, `NSCE_LTO`, `NSCE_AVX2`, `NSCE_SANITIZE`,
`NSCE_TSAN`, `NSCE_PGO_GENERATE`, `NSCE_PGO_USE`.

## Uso

```bash
./build/nsce
# UCI options: Hash, Threads, UseNNUE, UsePolicy, UseSearchController,
# EvalFile, PolicyFile, ControllerFile, TelemetryFile
```

```bash
ctest --test-dir build --output-on-failure
./build/nsce bench 6
python3 tools/smoke_match.py --games 2
bash train/run_train_loop.sh
```

## Laboratorio

```bash
bash tools/run_experiment_day.sh experiments/$(date +%Y%m%d)
# o por piezas:
python3 tools/ablation_match.py --matrix --games 100 --seed 1 --outdir experiments/$(date +%Y%m%d)
python3 tools/elo_ladder.py --outdir experiments/$(date +%Y%m%d)
python3 tools/sprt.py --cfg-b tools/configs/controller.uci --max-games 200 --seed 1
```

Los runners usan aperturas emparejadas con colores invertidos y escriben un
`manifest.json` reproducible. Baseline y protocolo: [docs/experiments.md](docs/experiments.md).

## Licencia

MIT. No incorporar código GPL (p. ej. Stockfish) en este árbol.
