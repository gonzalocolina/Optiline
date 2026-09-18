# Handoff — 2026-09-16

Read this, then [knowledge.md](knowledge.md). Knowledge is a log; this file is
what to do next. The north star is **equal-compute Stockfish 18** (same threads,
TC, hash), not a `UCI_Elo` handicap.

## State

- **Baseline:** `tools/configs/baseline.uci` —
  `EvalFile=nets/nnue_search_leaves40k_rw0.bin`, extras on, policy/controller
  off, Hash 16, `EvalScale=1000`. Engine NSCE 0.10. Frozen binary
  `build/nsce-frozen-20260915`. Bench `nsce_bench 12 1 1` that net:
  6 113 985 nodes, ~1.48 M nps.
- **Instrument:** `python3 tools/fastchess_match.py` (full games, resign/draw
  adjudication, 14 concurrent, pentanomial). Rebuild fastchess if missing:
  `git clone https://github.com/Disservin/fastchess third_party/fastchess && make -C third_party/fastchess -j`
  (gitignored). Pin SF with `third_party/stockfish/stockfish-18`, never PATH
  `stockfish` (that is SF17).
- **Gap:** vs unrestricted SF18 at 100 ms, full games: **0-1-99**
  ([report](../experiments/20260915_sf18_unlimited_100ms/report.md)). The
  promoted 768 is **+145 ± 45** vs the internal net with the same instrument
  ([report](../experiments/20260915_instrument_internal_full/report.md)).
  Limited SF18 Elo 2200 is a handicap rung, not a rating.
- **Why:** 40k search labels, NumPy CPU trainer, one-sided `768×128` plus
  `extras()` (~20 % of every node). Strong 1-person engines train ≥100 M
  positions on a dual-perspective net. Search constants are secondary.
- **Already in the tree:** `build/nsce_datagen` (bulletformat ChessBoard,
  ~170 pos/s/thread at 5k nodes ≈ 200 M/day on 14 threads), occupancy SEE,
  pawn-key cache. Source still has the blanket check extension; keep it
  (SPRT [0, 10] N=3000 inconclusive, LLR −0.44, +3.8 ± 10.2).

## Gate

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
ctest --test-dir build --output-on-failure -E 'PythonTrainTests'

# screen (≈ 30 min / 600 games)
python3 tools/fastchess_match.py --cfg-b tools/configs/<candidate>.uci \
  --st 100 --rounds 300 --outdir experiments/$(date +%Y%m%d)_<name>

# promote (SPRT [0, 5] nElo, default model)
python3 tools/fastchess_match.py --cfg-b tools/configs/<candidate>.uci \
  --tc 8+0.08 --sprt 0 5 --rounds 3000 --outdir experiments/$(date +%Y%m%d)_<name>_sprt

# vs unrestricted SF18
python3 tools/fastchess_match.py --engine-b third_party/stockfish/stockfish-18 \
  --cfg-b tools/configs/sf18_unlimited.uci --name-b sf18 --st 100 --rounds 50 \
  --outdir experiments/$(date +%Y%m%d)_sf18
```

Elo claims only from this harness. `ablation_match.py` / `sprt.py` with
`--max-plies 60` score truncated games as draws (~90 % of old gates). Keep
them for node/time telemetry. Never promote `baseline.uci` without pentanomial
H1. One change per SPRT. 768 extras on, or king-bucket extras off.

## Next (do in this order)

### P0 — Re-measure with the working instrument

**P0.1 done.** Drop blanket check extension: N=600 looked like candidate
**+23 ± 23**; SPRT [0, 10] N=3000 **inconclusive** (LLR −0.44, +3.8 ± 10.2).
Keep the extension. Promoted vs internal, vs unrestricted SF18, and staged
MovePicker are measured (see State).

**P0.2 done.** Re-measured leftover nets/flags whose old verdict was a
±15 coin flip. `fastchess_match.py --st 100 --rounds 300`, N=600, seed
20260915, `openings_balanced.epd`. One change per match. Old 60-ply rows
kept and annotated in [knowledge.md](knowledge.md). No `baseline.uci` change.

| Candidate | Config | Status |
| --- | --- | --- |
| `EvalScale=926` | `tools/configs/evalscale_926.uci` | **done** 225-149-226, −0.6 ± 21, N=600. Keep 1000. |
| Hash 32 on this 768 | `tools/configs/hash32_rw0.uci` | **done** 255-141-204, +29.6 ± 23, N=600. Hash 32 loses. Keep 16. |
| LMR controller | `tools/configs/controller_rw0.uci` | **done** 239-138-223, +9.3 ± 23.1, N=600. Coin flip. Keep controller off. |
| 40k mix λ=0.20 | `tools/configs/nnue_search_leaves40k.uci` | **done** 335-124-141, +116.5 ± 25.0, N=600. Candidate loses. Keep promoted rw0. |
| 80k@8000 rw0 | `tools/configs/nnue_search_leaves80k_rw0.uci` | **done** 235-133-232, +1.7 ± 24.1, N=600. Coin flip. Keep promoted 40k. |
| 640k static | `tools/configs/nnue_wdl_leaves640k.uci` | **done** 400-111-89, +199.4 ± 28.6, N=600. Static loses. Do not scale `--label static`. |

Skip: KAT 111-87-2, SF-teacher 768 N=400, extras-off H0, staged-picker
**−48 ± 31** full games. Those signs were decisive. Do not expect any of
these leftover nets to close >900 Elo vs unrestricted SF.

**P0.3 done (weekly KPI).** current `build/nsce` (sha256 `6bfe02eb…`, NSCEPER1
loader in tree) vs `build/nsce-frozen-20260915` (`503cff56…`), same
`baseline.uci`, `--tc 8+0.08`, `openings_uho.epd`, seed 20260915, N=300:
**129-45-126**, **+3.5 ± 20.7**. Coin flip. Binary change did not wreck the
768 path. ([report](../experiments/20260916_kpi_frozen/report.md)). 100 ms is
a screen. SF18 unlimited at 8+0.08 once draws appear.

**P0.4 done (book).** `tools/openings_uho.epd` (4096 unique 8-move / 16-ply
lines, NSCE `|eval|` 60–250 cp, seed 20260915). Default of
`tools/fastchess_match.py` (`--openings`). Four-field EPD without a glued
`;` on the EP square (fastchess rejects `f6;`). Leftover P0.2 screens stayed on
`openings_balanced.epd` so they match EvalScale/Hash 32. KPI and later
matches use the UHO book. Regenerate:
`python3 tools/generate_uho_book.py`.

### P1 — Bullet + 100 M datagen + (768→512)×2 SCReLU

`df -h .` first. 100 M bullet records ≈ 3.2 GB. Freed ~32 G by deleting
`leaves_with_results.jsonl` + sqlite (kept `train/data/nsce_search_mix_40k.jsonl`).
~42 G free as of 2026-09-16 (`df -h .`).
**P1 datagen resumed 2026-09-18 10:22.** `bash tools/resume_gen0.sh` append seed 4
(544 286 games) on `build-per1/nsce_datagen` from **49.7 M** records. ~3410 pos/s,
~4.1 h to 100 M. Watcher starts shuffle+bullet when the **file** is ≥100 M and 32-aligned.
Shuffle before bullet; do not fake a net. SPSA stays blocked until a P1 net exists.

```bash
./build-per1/nsce_datagen --out train/data/gen0.bin --games 689341 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 3
```

~12–14 h, ~100–120 M positions. Do not start the Python `selfplay.py` /
`collect_leaves.py` path for this generation.

Machine: GTX 1650 4 GB, CUDA. NumPy cannot ingest this scale.
Driver is 595 / CUDA 13.2 capable. nvcc 12.2 is unpacked without sudo:

```bash
bash tools/setup_cuda_local.sh            # third_party/cuda-12.2 from local debs
bash tools/watch_datagen_then_train.sh    # after gen0 done and ≥100 M positions
bash train/run_bullet.sh                  # shuffle + CUDA train + pack + float-ref + 100 ms screen
```

`bash tools/setup_bullet.sh` is done. CUDA `nsce` example and `bullet-utils` are in
`third_party/bullet/target/release/`. Train uses batch 8192 (GTX 1650 4 GB).
Shuffle/train wait for `gen0.bin` to finish.

```bash
# rustup + CUDA toolkit if missing
git clone https://github.com/jw1912/bullet third_party/bullet
# copy examples/simple.rs → examples/nsce.rs, register in crates/bullet_lib/Cargo.toml
# HIDDEN_SIZE=512, .dual_perspective(), inputs::Chess768, SCReLU
# QA=255 QB=64 SCALE=400, λ=0.75 score/WDL, 8 output buckets (popcount(occ)-2)/4
cargo r -r --example nsce --features cuda
cargo b -r --package bullet-utils   # shuffle | interleave | validate
```

Shuffle `gen0.bin` before training. Docs: bullet `progression/2-output-buckets.md`.

**Inference (`NSCEPER1`):** two 512-int16 accumulators (white / black
perspective). Feature `perspective_piece * 64 + oriented_sq` (768,
king-agnostic). Output = Σ SCReLU(acc_stm)·w_stm + Σ SCReLU(acc_nstm)·w_nstm
per bucket `(popcount-2)/4`. AVX2 SCReLU (int32 square, int64 add; aligned
`w1`). Loaded in `engine/src/nnue.cpp`; pack with
`python3 tools/pack_nsceper1.py --from-quantised train/bullet_checkpoints/nsce-320/quantised.bin`.
Then `python3 tools/per1_float_ref.py --net nets/nsceper1.bin --n 10000` (UseExtras
off; quantized Python == C++; |float−C++| ≤ 2 cp) before any match on a packed net. Rebuild Release
when no timed match is using `build/nsce`. Do not fake a trained net;
extras-off is after a winning net; gen1 after H1. Train: 8 loader threads,
batch queue 64, shuffle 4 GiB (`NSCE_THREADS` / `NSCE_QUEUE` / `SHUFFLE_MB`).
GTX 1650 measured **~448 k pos/s** on an 8192×2 smoke (2 loader threads);
320 × 100 M superbatches ≈ **22 h** after gen0 finishes. Training resumes from
the last `nsce-*` optimiser_state (`NSCE_RESUME=0` to start over). Shuffle is
skipped when `gen0.shuffled.bin` already matches gen0.bin size. `run_bullet.sh`
retries the CUDA example up to 40 times so a driver drop does not abandon a
22 h run.

Expected: several hundred Elo over the promoted 768. Then measure
`UseExtras=false` — do not assume extras can drop.

Gate: `run_bullet.sh` runs `--st 100 --rounds 500` after float-ref (same
`build-per1/nsce` that passed the export check). If extras-on is a clear loss
(Elo A−B CI entirely ≥ +20), it measures `UseExtras=false` next — do not
assume extras can drop, and do not skip that measurement. Then `--tc 8+0.08 --sprt 0 5`
If H1, `python3 tools/promote_eval.py --sprt <match.json> --manifest <manifest.json>`
updates `baseline.uci` (EvalFile, and UseExtras only if that was the winning candidate).
Each generation packs to `nets/nsceper1_genN.bin` and screens a UCI that points at that
file — it must not overwrite a promoted EvalFile. `run_gen1.sh` reads the promoted
path from `baseline.uci`. `run_bullet.sh` runs that SPRT itself after a non-loss 100 ms screen, then extras-off
after an extras-on H1, then `run_gen1.sh` unless `NSCE_SKIP_SPRT` / `NSCE_SKIP_GEN1`.
Then gen1:
regenerate with the new net, retrain, repeat (~3 generations). King buckets /
hidden 1024 / threats only after gen1 wins.
KAT on 1 M Lichess roots is not evidence against king-relative inputs.

### P2 — SPSA, not hand-tuned constants

**In tree (not run yet):** 44 search constants in `engine/include/nsce/tune.hpp`,
UCI spins behind CMake `-DNSCE_TUNE=ON` (`build-tune/nsce` copied to
`build/nsce-tune`, `RazorMargin` advertised). weather-factory map
`tools/configs/spsa.json`. Defaults match the 2026-09-15 source. Do not SPSA until P1 gen0 net exists; then
`bash tools/run_spsa.sh` (~30k games/pass at 8+0.08). Re-run after every net
generation. weather-factory `cutechess.py` takes `extra_uci` so both engines
load the promoted PER1 `EvalFile` / `UseExtras` from baseline, not the engine default.

Then one feature per SPRT [0, 5] at 8+0.08:

1. Staged move picker (TT → good captures → killers → quiets → bad captures;
   score quiets only when that stage starts). Rewrite from scratch; do not
   revive `build-nps/nsce` (−48 ± 31 at equal time, full games).
2. History-scaled LMR (`R -= hist / 8192`)
3. `ttPv` + PV-node reductions; cut-node +2 with no TT move
4. Material / minor / major correction histories
5. QS checks at depth 0; TM from best-move node fraction

Lazy SMP (shared TT, staggered helper depths) only when the target is
equal-compute SF at Threads > 1.

### P3 — Lab

- [eval_pipeline.md](eval_pipeline.md) step 3 is fixed-node self-play ≥100 M +
  bullet + `NSCEPER1` (**verified 2026-09-16** against this handoff).
  Clone-export and deployed-integer gates stay. `selfplay.py` /
  `collect_leaves.py` / `distill.py --label static` marked legacy in
  `train/README.md`. `promotion_gate.py` accepts fastchess H1 JSON.
- Commit the dirty tree (dirty since 2026-08-27) before a long datagen so
  `manifest.json` `git.commit` is meaningful. Do not commit unless asked.

## Do not

- Elo from `ablation_match.py` / `sprt.py` with `--max-plies 60`.
- `--label static` nets of any size (cannot beat the arbiter they clone).
- Scale the NumPy trainer. Scale data with `nsce_datagen` + bullet.
- `UCI_Elo` ladder rungs as a strength claim.
- Hand-tune search constants one-at-a-time at 100 ms.
- Drop the blanket check extension (SPRT [0, 10] N=3000 inconclusive,
  +3.8 ± 10.2). N=600 LOS 97 % did not hold.
- Promote / replay `build-nps/nsce`, KAT bins, SF-teacher 768, extras-off on
  this 768, Hash 32, `EvalScale≠1000`, policy, the LMR controller, 40k λ=0.20,
  80k rw0, or 640k static. P0.2 did not produce a new sign to promote.
- Port GPL Stockfish search or load Stockfish `.nnue` weights. Labels are
  allowed; weights and search clones are not.
- Lazy SMP, king buckets, hidden 1024, or threat inputs before P1 gen1 wins.
- Skip the weekly frozen KPI. Datagen is next after P0.3 is running (leftover
  cores) or finished; do not oversubscribe a timed match.
