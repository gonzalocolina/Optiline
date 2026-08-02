# Measurement and architecture scorecards

NSCE now separates four measurement layers:

1. **Correctness** — perft, tactical/mate tests, ASan/UBSan.
2. **Fixed-work cost** — `nsce_bench` and Callgrind/`perf` on fixed depth suites.
3. **Search quality** — telemetry and UCI ablation flags at equal nodes/time.
4. **Playing strength** — paired openings, pentanomial SPRT, diverse books.

## Telemetry (`NSCE_STATS`)

```bash
cmake -S . -B build-stats -DCMAKE_BUILD_TYPE=Release -DNSCE_STATS=ON -DNSCE_LTO=OFF
cmake --build build-stats -j
./build-stats/nsce_bench 10 1 1
```

Counters are local to each worker and aggregated after search:

- TT probes / hits / cutoffs
- first-move cutoff percentage and mean cutoff index
- LMR attempts / researches
- null / razor / RFP / futility / LMP
- qnodes and evaluations
- SEE order / prune / successful prune counts
- root moves claimed in parallel root split

When enabled, UCI also emits:

```text
info string stats qnodes_pct ... tt ... first_cut_pct ... lmr ... see ...
```

## Ablation flags

Baseline freezes every search feature. Toggle candidates with:

| Option | Meaning |
| --- | --- |
| `UseTT` | transposition table probe/store |
| `UseSEE` | SEE ordering and losing-capture prune |
| `UseLMR` | late-move reductions |
| `UseNullMove` | null-move pruning |
| `UseFutility` | futility pruning |
| `UseLMP` | late-move pruning |
| `UseRazoring` | razoring |
| `UseRFP` | reverse futility pruning |

```bash
python3 tools/ablation_match.py --search-matrix \
  --openings tools/openings_balanced.epd \
  --games 40 --movetime 100 --seed 20260802 \
  --outdir experiments/$(date +%Y%m%d)_search_ablation
```

Interpret equal-node and equal-time results separately. A feature that wins fixed nodes but loses fixed time is too expensive, not necessarily wrong.

## Profiling

```bash
bash tools/profile_engine.sh
```

On this host, `kernel.perf_event_paranoid=4` blocks hardware counters for unprivileged users. Fallback:

```bash
valgrind --tool=callgrind --callgrind-out-file=experiments/profiles/search.callgrind \
  ./build-stats/nsce_bench 7 1 1
callgrind_annotate --inclusive=yes experiments/profiles/search.callgrind
```

Observed exclusive hotspot before slider tables: `rook_attacks_bb` ≈ 15% of instructions. After magic/PEXT tables, perft(6) improved from ≈2143 ms to ≈1765 ms (−18%).

## Parallelism measurement

Use the multi-position bench with thread count as the second argument:

```bash
./build-stats/nsce_bench 10 1 1
./build-stats/nsce_bench 10 4 1
```

Root workers are now persistent for the whole `go`. Report wall-time, nodes and CPU efficiency separately; more nodes alone is not a strength claim.

## HalfKP / king-bucket path

Runtime accepts both formats:

- `NSCENNUE` — current piece-square 768×128×1 network
- `NSCEHFKP` — 16 king buckets × 768 features × two perspectives

Train only after a large labeled corpus:

```bash
.venv/bin/python train/train_halfkp.py \
  --data train/data/nnue_stockfish_d8.jsonl \
  --minimum-samples 50000
```

The default minimum (50k) intentionally rejects the current 2k bootstrap. A smoke export may be built with `--minimum-samples 20` for runtime validation only.

## Lab protocol upgrades

- `tools/generate_openings.py` creates teacher-balanced diverse FENs.
- `tools/openings_balanced.epd` (128 positions) is the preferred exploratory book.
- `tools/sprt.py` now uses a **pair-level pentanomial** LLR and refuses resume from the older trinomial model.

Promotion still requires a fresh pre-registered SPRT at a non-exploratory time control.
