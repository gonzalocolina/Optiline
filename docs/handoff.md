# Handoff — after Phase 1 P0 contracts

Operational notes for the next agent. Architecture thesis:
[synthesis canvas](/home/gonzalo/.cursor/projects/home-gonzalo-Escritorio-Codigo-Optiline/canvases/nsce-architecture-synthesis.canvas.tsx)
and [knowledge.md](knowledge.md). Do not start king-relative / Bullet / Lazy SMP /
policy until the items below.

## Phase 1 (done)

Correctness contracts so later Elo gates are readable:

- **TT eval:** quiescence and search store **raw** `evaluate_for_search()` in TT.
  Correction is applied once at the consumer (`compose_search_eval` /
  `raw_eval_from_tt` in `engine/include/nsce/search.hpp`). Leaf `score_cp`
  remains the tree-used (corrected) stand-pat/static score.
- **FEN:** exactly one king per color; castling flags must match king+rook home
  squares (throw). Illegal EP squares canonicalize to none.
- **UCI:** `UseExtras` copies into `Search::root_` via `set_position`.
  `Nnue::load` / `load_default_from_hce` swap a complete net and do **not**
  force `enabled_=true`. `EngineContext::nnue_wanted` tracks `UseNNUE`.

`tools/configs/baseline.uci` is unchanged.

### Re-run tests

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DNSCE_LTO=OFF
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure -E 'PythonTrainTests'

cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DNSCE_LTO=OFF -DNSCE_SANITIZE=ON -DNSCE_NATIVE=OFF
cmake --build build-asan -j"$(nproc)" --target nsce_tests
ctest --test-dir build-asan --output-on-failure -E 'PythonTrainTests|UciSmoke|SearchBenchSmoke|NnueBenchSmoke|ComponentsBenchSmoke'
```

`PythonTrainTests` needs numpy in the runner’s Python; it is unrelated to P0.

### TT-eval diagnostic (search-behavior change)

Old binary (`build/nsce-p0-before`, pre-P0) vs new (`build/nsce`), same UCI:

```bash
python3 tools/ablation_match.py \
  --engine build/nsce-p0-before --engine-b build/nsce \
  --cfg-a tools/configs/baseline.uci --cfg-b tools/configs/baseline.uci \
  --games 200 --nodes 25000 --seed 20260814 \
  --openings tools/openings_balanced.epd \
  --outdir experiments/20260827_tt_eval_raw
```

**Ran 2026-08-27.** Pre-P0 (A) vs P0 (B): **13-177-10**, score A 0.507,
**+5 ± 17**, 25k nodes, N=200, seed 20260814
([report](../experiments/20260827_tt_eval_raw/report.md)). Diagnostic coin
flip; no equal-time SPRT. Logged under Findings in [knowledge.md](knowledge.md);
Current beliefs unchanged.

If `nsce-p0-before` is missing, the pre-P0 tree is git history before this
slice; do not compare two copies of the new binary.

## Do not do next

- King-relative / KAT / HalfKP training or SPRT
- Bullet trainer integration
- Lazy SMP / replacing root-claim workers
- Policy or LMR controller on
- Stockfish `.nnue` files, SFNNv16 features, extras off on the 768 net
- Replay `kat_candidate.bin` at 100 ms

Rejected table: [knowledge.md](knowledge.md).

## Next work, in order

### 1. Leaf-label provenance

[`train/collect_leaves.py`](../train/collect_leaves.py) `stamp_leaf` copies a
finished-game WDL onto hypothetical search leaves. Keep **played-path** and
**search-leaf** labels separate; sample by game/phase/site. Unfinished games
stay unlabeled (`result` absent).

### 2. 80k 768 protocol (cheap, expected coin flip)

After P0 is in the binary used for labeling/search:

- Uniform sample of `train/data/leaves_with_results.jsonl` (already on disk,
  4.6M unique) — **80k**, not another 20k.
- `768×128`, extras **on**, `--init internal --augment mirror`,
  `result-weight 0.20`, NSCE WDL coin ([eval_pipeline.md](eval_pipeline.md)
  steps 5–7).
- Equal-node N≥200 vs frozen baseline, then equal-time only if clearly above
  0.5. Do not block datagen on this run.

### 3. Datagen toward 100M leaves

Streaming self-play, exact NSCE WDL, unfinished games unlabeled. The 4.6M dump
is a start, not a corpus. Optional NPS work (staged MovePicker, SEE reuse) is a
**separate** candidate from any net.

### 4. Frozen Stockfish targets before any new ladder

Refresh [`experiments/frozen-targets/manifest.json`](../experiments/frozen-targets/manifest.json)
to official **Stockfish 18** and **stockfish-dev-20260825-2edd935b**. Never
resolve `stockfish` from PATH (that was SF17). Stay on SF18 Elo 2000, N≥40
until a **promoted** eval wins that rung. Unrestricted equal-compute SF is
still unplayed.

### 5. Only after an eval H1

King-relative `704×16` hm, extras off, Bullet (MIT), grouped search-margin
retune in the same candidate. Then Lazy SMP before multi-thread SF. Then
accumulator-conditioned policy.
