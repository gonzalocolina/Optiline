# Optiline (NSCE) — C++20 Chess Engine with Quantized NNUE Evaluation

[![CI](https://github.com/gonzalocolina/Optiline/actions/workflows/ci.yml/badge.svg)](https://github.com/gonzalocolina/Optiline/actions)
![C++20](https://img.shields.io/badge/Language-C%2B%2B20-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)
![SIMD](https://img.shields.io/badge/Optimization-AVX2%20%2F%20int16-orange.svg)
![License](https://img.shields.io/badge/License-GPLv3-lightgrey.svg)

Optiline (engine name: **NSCE**) is a high-performance chess engine combining classical alpha-beta search with an **Efficiently Updatable Neural Network (NNUE)**. Designed for low-compute environments, it achieves sub-microsecond evaluation throughput via incremental feature accumulators, int16 quantization, and hand-tuned AVX2 vectorization.

---

### Key Benchmarks

| Metric | Specification / Result |
| :--- | :--- |
| **Playing Strength** | **+145 Elo** vs. Stockfish 18 (limited to 2200) @ 100 ms/move |
| **Statistical Validation** | SPRT (Sequential Probability Ratio Test) via `fastchess` |
| **Evaluation Latency** | Optimized for millions of evaluations/sec on single-core CPU |
| **Protocols** | UCI (Universal Chess Interface) + embedded web GUI |

---

### Systems & ML Architecture

In high-depth tree search, evaluation latency dominates playing strength. The architecture is engineered around the ML-Systems trade-off: **model expressiveness vs. inference throughput**.

```
[ Board State ] 
       │
       ▼ (sparse update)
[ Incremental Feature Accumulator ] ──► Updates only moved/captured pieces O(1)
       │
       ▼ (int16 / AVX2 SIMD)
[ Quantized Feed-Forward Network ] ──► Multi-bucket evaluation head
       │
       ▼
[ Centipawn Score ] ──► Consumed by PVS / Alpha-Beta search loop
```

#### 1. Machine Learning Pipeline (`/train`)
* **Representations:** 768 sparse piece-square features, HalfKP, and king-relative (KAT/PER1) architectures with pairwise CReLU and SCReLU activations.
* **Quantization-Aware Training (QAT):** Emulates int16/int8 fixed-point arithmetic during the forward pass using straight-through estimators, preventing precision mismatch when exporting to C++.
* **Dataset & Distillation:** Teacher-student distillation using game targets (WDL) generated from self-play and engine evaluation datasets, split by opening/game source to prevent train-test contamination.
* **Gating via Game Play (SPRT):** Checkpoints are not promoted purely on validation loss/MAE; candidate networks must pass automated full-game SPRT matches against baselines.

#### 2. Engine & Systems Optimization (`/engine`)
* **Incremental Accumulators:** Piece moves update only the altered input weights rather than recomputing the full 768-feature layer from scratch.
* **Vectorized Kernels:** AVX2-accelerated fused multiply-add operations operating on quantized integer weights.
* **Search Infrastructure:** Principal Variation Search (PVS), Quiescence search, Transposition Tables (TT), and adaptive move ordering heuristics.

---

### Repository Structure

```text
├── engine/             # C++20 engine source
│   ├── src/nnue/       # SIMD inference, accumulators, quantized layers
│   ├── src/search/     # Alpha-beta, PVS, move ordering, transposition tables
│   └── benches/        # Component-level latency benchmarks
├── train/              # ML training & data pipeline
│   ├── train_nnue.py   # QAT, model definitions (768, PER1), binary weight export
│   └── datagen.py      # Self-play and dataset formatting
├── tools/              # Automated SPRT, fastchess wrappers, Elo calculation
└── .github/workflows/  # CI: Release, ASan/UBSan, TSan, and multi-threaded tests
```

---

### Quickstart

#### Build & Run CLI
Requires a C++20 compiler and CMake:
```bash
# Build optimized binary
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

# Run interactive CLI (or connect via UCI to CuteChess/Arena)
./build/nsce
```

#### Run Web Interface
Launch the engine with the local web interface at `http://127.0.0.1:8765/`:
```bash
./play.sh
```

#### Run Tests & Sanity Checks
```bash
ctest --test-dir build --output-on-failure
```

---

### Engineering & Quality Assurance

All commits pass an automated test matrix:
* **Memory & Thread Safety:** Instrumented with `AddressSanitizer (ASan)`, `UndefinedBehaviorSanitizer (UBSan)`, and `ThreadSanitizer (TSan)`.
* **Reproducible Evaluation:** Match manifests, PGN logs, and SPRT stopping bounds are tracked under `/experiments`.

---

### License

Distributed under the [GNU General Public License v3.0](LICENSE).
