# NSCE — Neural Search Chess Engine

Motor de ajedrez UCI en C++20. Hipótesis: una política neuronal de presupuesto de búsqueda puede ganar Elo a igual CPU/tiempo frente a Stockfish.

## Estado actual (v0.8)

- Núcleo bitboard + perft + UCI
- Búsqueda competitiva (NMP, LMR, aspiration, futility, Lazy SMP)
- NNUE incremental int16 (+ AVX2), política de ordenación, controlador de reducciones + telemetría
- Autojuego y fit de redes (`train/`)
- Optimización: `-O3`, `-march=native`, LTO, prefetch TT, PGO opcional

## Build

```bash
export PATH="$HOME/.local/bin:$PATH"
cmake -G "Unix Makefiles" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
cmake --build build -j"$(nproc)"
```

Opciones CMake: `NSCE_NATIVE`, `NSCE_LTO`, `NSCE_AVX2`, `NSCE_PGO_GENERATE`, `NSCE_PGO_USE`.

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

## Documentación

- [Hipótesis y protocolo](docs/hypothesis.md)
- [Roadmap](docs/roadmap.md)

## Licencia

MIT. No incorporar código GPL (p. ej. Stockfish) en este árbol.
