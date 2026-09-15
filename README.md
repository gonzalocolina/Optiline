# NSCE — Neural Search Chess Engine

Motor de ajedrez UCI en C++20. Hipótesis: ganar Elo a **igual CPU, hilos y
tiempo** frente a Stockfish. El norte es Stockfish 18 sin `UCI_Elo`, no un
peldaño con hándicap.

## Estado actual (v0.10)

- Movegen legal pin-aware (doble jaque, evasiones y en-passant) validado con perft
- PVS/alpha-beta con IIR, ProbCut, NMP verificado, extensiones singulares dobles,
  continuation 1/2/4/6, capture/correction history y pick-next
- QS fail-soft, SEE sobre ocupancia (sin copiar el tablero) y cache de estructura
  de peones
- Telemetría `NSCE_STATS`, flags de ablación y tablas de ataques magic/PEXT
- NNUE promovida `768×128×1` (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`) más
  residual clásico `extras()`. El árbitro interno queda en
  `tools/configs/baseline_internal.uci`
- Runtime HalfKP (`NSCEHFKP`) y KAT (`NSCEKAT1`); no son el baseline
- **Instrumento de Elo:** `tools/fastchess_match.py` (partidas completas,
  adjudicación, pentanomial). `ablation_match.py` / `sprt.py` a `--max-plies 60`
  cuentan el corte como tablas (~90 % de las puertas viejas) y no sirven como
  veredicto de fuerza
- Frente a Stockfish 18 sin límite, 100 ms, partidas completas: **0-1-99**
  (> 900 Elo). La misma 768 es **+145 ± 45** contra la red interna
- Datagen en el motor: `build/nsce_datagen` (bulletformat, ~200 M pos/día)
- Optimización: AVX2, LTO, `-march=native`, pool SMP persistente entre `go`

Siguiente trabajo: [docs/handoff.md](docs/handoff.md). Modelo del laboratorio:
[docs/knowledge.md](docs/knowledge.md).

## Build

```bash
export PATH="$HOME/.local/bin:$PATH"
cmake -G "Unix Makefiles" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
cmake --build build -j"$(nproc)"
```

Opciones CMake: `NSCE_NATIVE`, `NSCE_LTO`, `NSCE_AVX2`, `NSCE_SANITIZE`,
`NSCE_TSAN`, `NSCE_STATS`, `NSCE_PGO_GENERATE`, `NSCE_PGO_USE`.

Stockfish 18 está en `third_party/stockfish/stockfish-18` (gitignored). Nunca
usar el `stockfish` del PATH (en esta máquina es SF17).

## Uso

```bash
./build/nsce
# UCI: Hash, Threads, UseNNUE, UsePolicy, UseSearchController,
# EvalFile, PolicyFile, ControllerFile, TelemetryFile, EvalScale,
# UseTT, UseSEE, UseLMR, UseNullMove, UseFutility, UseLMP, UseRazoring, UseRFP, UseProbCut
./tools/play.sh                # tablero en http://127.0.0.1:8765/ (abre esa URL tú)
./tools/play.sh --cli          # lo mismo en terminal (e4, Nf3 o e2e4)
```

Baseline congelado: `tools/configs/baseline.uci` (Hash 16, extras on, política y
controlador off, `EvalScale=1000`).

```bash
ctest --test-dir build --output-on-failure -E 'PythonTrainTests'
./build/nsce_bench 12 1 1 nets/nnue_search_leaves40k_rw0.bin
```

## Laboratorio

Elo solo con partidas completas:

```bash
git clone https://github.com/Disservin/fastchess third_party/fastchess
make -C third_party/fastchess -j

# pantalla (~30 min / 600 partidas)
python3 tools/fastchess_match.py --cfg-b tools/configs/<candidate>.uci \
  --st 100 --rounds 300 --outdir experiments/$(date +%Y%m%d)_<name>

# promocionar (SPRT [0, 5] nElo)
python3 tools/fastchess_match.py --cfg-b tools/configs/<candidate>.uci \
  --tc 8+0.08 --sprt 0 5 --rounds 3000 --outdir experiments/$(date +%Y%m%d)_<name>_sprt

# vs Stockfish 18 sin límite
python3 tools/fastchess_match.py --engine-b third_party/stockfish/stockfish-18 \
  --cfg-b tools/configs/sf18_unlimited.uci --name-b sf18 --st 100 --rounds 50 \
  --outdir experiments/$(date +%Y%m%d)_sf18
```

Datagen a escala (no el bucle Python `selfplay.py` / `collect_leaves.py`):

```bash
./build/nsce_datagen --out train/data/gen0.bin --games 1200000 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1
```

Un cambio por SPRT. 768 con extras on, o red de rey con extras off. No
promocionar `baseline.uci` sin H1 pentanomial.

Protocolo: [docs/handoff.md](docs/handoff.md),
[docs/eval_pipeline.md](docs/eval_pipeline.md),
[docs/measurement.md](docs/measurement.md),
[docs/experiments.md](docs/experiments.md).
Entrenamiento (clon + legado NumPy): [train/README.md](train/README.md).

## Licencia

MIT. No incorporar código GPL (p. ej. Stockfish) en este árbol. Etiquetas de
profesor sí; pesos `.nnue` y clones de búsqueda no.
