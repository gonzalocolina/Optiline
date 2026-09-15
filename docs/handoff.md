# Handoff — 2026-09-15

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

**P0.2 — start here.** Re-measure leftover nets/flags whose old verdict was a
±15 coin flip and whose file still exists. `fastchess_match.py --st 100
--rounds 300`. One change per match. Update the Rejected table with the new
numbers; do not delete old 60-ply rows, annotate them.

| Candidate | Config | Old 60-ply verdict |
| --- | --- | --- |
| `EvalScale=926` | `tools/configs/evalscale_926.uci` | 10-176-14, −7 ± 17 |
| Hash 32 on this 768 | `tools/configs/hash32_rw0.uci` | Hash 32 vs *internal* was inconclusive |
| LMR controller | `tools/configs/controller_rw0.uci` | 9-182-9, +0 ± 15 |
| 40k mix λ=0.20 | `tools/configs/nnue_search_leaves40k.uci` | won nodes, failed SPRT |
| 80k@8000 rw0 | `tools/configs/nnue_search_leaves80k_rw0.uci` | 9-180-11, −3 ± 16 |
| 640k static | `tools/configs/nnue_wdl_leaves640k.uci` | 12-181-7, +9 ± 15 |

Skip: KAT 111-87-2, SF-teacher 768 N=400, extras-off H0, staged-picker
**−48 ± 31** full games. Those signs were decisive. Do not expect any of
these leftover nets to close >900 Elo vs unrestricted SF.

**P0.3** after P0.2: drop the `UCI_Elo` ladder as a strength claim. Weekly
KPI = Elo vs `build/nsce-frozen-20260915` at `--tc 8+0.08`. 100 ms is a
screen. SF18 unlimited at 8+0.08 once draws appear.

**P0.4** larger UHO-style 8-move EPD book in `tools/`; `openings_balanced.epd`
is 128 lines (repeats on long SPRTs). Point `fastchess_match.py` at it.

### P1 — Bullet + 100 M datagen + (768→512)×2 SCReLU

`df -h .` first. 100 M bullet records ≈ 3.2 GB. `train/data/` holds ~37 GB of
JSONL leaves with no remaining consumer. Keep the 40k promoted mix; archive
or delete the rest of `leaves*.jsonl`.

```bash
./build/nsce_datagen --out train/data/gen0.bin --games 1200000 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1
```

~12–14 h, ~100–120 M positions. Do not start the Python `selfplay.py` /
`collect_leaves.py` path for this generation.

Machine: GTX 1650 4 GB, CUDA. NumPy cannot ingest this scale.

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
per bucket. Quantise as bullet documents. Float-ref vs C++ on 10k FENs, max
abs error ≤ 1 cp, before any match.

Expected: several hundred Elo over the promoted 768. Then measure
`UseExtras=false` — do not assume extras can drop.

Gate: `--st 100 --rounds 500`, then `--tc 8+0.08 --sprt 0 5`. If H1, promote
`EvalFile`. Then gen1: regenerate with the new net, retrain, repeat (~3
generations). King buckets / hidden 1024 / threats only after gen1 wins.
KAT on 1 M Lichess roots is not evidence against king-relative inputs.

### P2 — SPSA, not hand-tuned constants

Expose ~40 search constants as UCI `spin` behind `NSCE_TUNE` (OpenBench
`name, int, default, min, max, step, lr`). Tune with
[weather-factory](https://github.com/jnlt3/weather-factory) over fastchess at
8+0.08, ~30k games/pass. Re-run after every net generation.

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

### P3 — Lab (does not block P0.2)

- Rewrite [eval_pipeline.md](eval_pipeline.md) step 3 to “fixed-node self-play
  ≥ 100 M”; keep clone-export and deployed-integer gates; drop static-label
  scale-up. Mark `selfplay.py` / `collect_leaves.py` / `distill.py --label static`
  as legacy in `train/README.md`.
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
  this 768, Hash 32, `EvalScale≠1000`, policy, or the LMR controller **until
  P0.2 gives a new sign**.
- Port GPL Stockfish search or load Stockfish `.nnue` weights. Labels are
  allowed; weights and search clones are not.
- Lazy SMP, king buckets, hidden 1024, or threat inputs before P1 gen1 wins.
- Skip P0.2 to start P1. The leftover coin-flips still need a working
  instrument; then datagen.
