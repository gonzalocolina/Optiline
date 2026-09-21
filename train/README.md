# Training pipeline

**Elo path (2026-09-15):** `build/nsce_datagen` (bulletformat, ≥100 M positions)
then a bullet trainer, not this NumPy loop. Gate with
`python3 tools/fastchess_match.py` (full games).

`selfplay.py`, `collect_leaves.py`, `distill.py --label static`, and
`train/run_datagen.sh` are **legacy**. They built the promoted 40k mix; do not
scale `--label static` further. `ablation_match.py` / `sprt.py` with
`--max-plies 60` are telemetry only.

Evaluator export still has to clone: quantized C++ must match the frozen
768×128 notes before any Elo gate.

## 0. Engine datagen (current)

```bash
./build/nsce_datagen --out train/data/gen0.bin --games 1200000 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1
```

Shuffle with bullet-utils before training. Example: `train/bullet_nsce.rs`
(`bash tools/setup_bullet.sh`). Runtime loads `NSCEPER1`; pack a quantised
checkpoint with `python3 tools/pack_nsceper1.py`. Do not start the Python
self-play path for a new generation.

## 1. Clone the frozen arbiter (export check)

Static C++ eval (internal net + extras), same `768×128`, quantized binary must
reproduce those notes. This is an export/sanity gate, not the Elo path.

```bash
bash train/run_clone_arbiter.sh
```

`--label static` is `eval details`, not `go nodes`. `--residualize-extras` is
mandatory on the 768 path because runtime adds extras(). Teacher cp is converted
with `--teacher-wdl-scale` (that teacher) into `--search-wdl-scale` (NSCE search
coin). Clone uses `--target-mode cp` because the teacher already is NSCE.

## Legacy Python self-play / leaves (do not scale)

`selfplay.py`, `collect_leaves.py`, `distill.py --label static`, and
`train/run_datagen.sh` built the promoted 40k mix. They are **not** the Elo
path. Do not collect more JSONL leaves. New data: `nsce_datagen` (above).

```bash
python3 train/selfplay.py --games 8 --movetime 80 --both-colors \
  --config tools/configs/baseline.uci \
  --positions-out train/data/selfplay_positions.jsonl
```

Uses UCI `status` (`checkmate` / `stalemate` / `draw` / `ongoing`). A `max_plies`
cutoff is **not** a draw: those positions are written without `result` so WDL mix
does not treat an aborted game as 1/2-1/2. Path FENs from those games were
equal-node coin flips. Search leaves keep provenance but **not** the game WDL:

```bash
python3 train/collect_leaves.py --games train/data/selfplay_colors.jsonl \
  --limit 0 --positions-per-game 3 --nodes 25000 \
  --output train/data/leaves_with_results.jsonl
```

`--strip-results` rewrites an older dump so only played-path FENs keep `result`.
`--path-output` writes those path FENs without searching. `--append` plus the
`.seen.sqlite` index skips roots already collected. `WORKERS` also parallelizes
those root searches (one `Threads=1` engine each; uniqueness stays in the parent
sqlite). That is not Lazy SMP. Telemetry is rewound after each search so the raw
dump cannot fill the disk. Collect refuses to start, and stops `--append`-safely,
if free space drops below 512 MB.

Streaming increment (resume self-play, then append leaves):

```bash
TARGET_GAMES=512 MOVETIME=100 bash train/run_datagen.sh
```

Prefer balanced openings, not random walks and not the first slice of a dump.
Default `--max-plies` is 200. Self-play is one 1-thread engine per game;
`WORKERS` (default `nproc-1`) runs independent games in parallel, then the same
count of leaf-root searches. That is not Lazy SMP and does not change
`baseline.uci`.

## Trained NNUE (after the clone pipe works)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install numpy

.venv/bin/python train/train_nnue.py \
  --data train/data/nsce_static_games.jsonl \
  --epochs 80 --seed 20260802 --target-mode wdl \
  --teacher-wdl-scale 400 --search-wdl-scale 400 \
  --result-weight 0.20 --residualize-extras --init internal

.venv/bin/python train/validate_nnue.py \
  --engine build/nsce --data train/data/nsce_static_games.jsonl \
  --network nets/nnue_trained.bin --use-extras --gate clone
```

`train_nnue.py` trains the exact `768x128x1` topology consumed by C++. It converts
teacher CP with that teacher's WDL curve into the NSCE search coin, optionally
blends a recorded game result, peels extras when the 768 runtime will add them
back, splits by source game/opening group, augments only the training split,
and performs fake integer forward quantization with straight-through gradients by
default. `--no-qat` is available only for diagnostic comparisons. Training
symmetries are `--augment none|mirror|full` (default `mirror`). Color-flip
(`full`) is not a symmetry of this ReLU net and walks off `--init internal`.
It restores the best frozen-validation epoch, **including epoch 0**, exports
`NSCENNUE`, and rejects conservative int16
accumulator overflow. `--init internal` starts from the frozen HCE default instead
of random weights (also accepts a `.npz` checkpoint or an `NSCENNUE` `.bin`).
Training batches are packed sparse active-feature rows and generate symmetry
variants on demand; `--dense-legacy` is retained only for controlled regression
comparisons.

MAE on float or C++ integers rejects wreckage; it does not promote. Promotion is
a full-game fastchess SPRT (`--tc 8+0.08 --sprt 0 5`), one UCI change, extras
contract. The 2k bootstrap is not that gate.

## HalfKP / king-bucket path (`NSCEHFKP`)

Runtime already loads `NSCEHFKP` (16 king buckets, dual accumulators, refresh on king
moves). Train only after a large labeled corpus:

```bash
.venv/bin/python train/train_halfkp.py \
  --data train/data/nnue_stockfish_d8.jsonl \
  --epochs 40 --seed 20260802 \
  --minimum-samples 50000
```

The default `--minimum-samples 50000` rejects the 2k bootstrap on purpose. For runtime
smoke tests only:

```bash
.venv/bin/python train/train_halfkp.py \
  --data train/data/nnue_stockfish_d8.jsonl \
  --epochs 2 --minimum-samples 20 \
  --out nets/nnue_halfkp_smoke.bin
```

Do not promote smoke nets. Prefer a fresh distill of ≥50k positions before any SPRT.

## KAT — king-relative base first (`--no-threats`), then threats

Illegal until the 768 clone (and then a winning 768) has passed the export
and Elo gates. The first richer net
is HalfKA-hm **without** the 12-dim threat residual. Threats, hidden 256, policy
and hardware come after that base wins SPRT.

- 32 horizontally-mirrored king buckets (king forced onto files e–h)
- Train-time piece-square factorization, folded into the sparse table at export
- 12-dim threat residual is **off** for the first candidate (`--no-threats`)
- Labels already on the NSCE search coin; extras stay off
- WDL/logit targets and fake integer forward are enabled by default; use
  `--target-mode cp` only for an explicitly registered clone comparison.

```bash
# ≥50k (then millions) from Lichess evals. Stream; do not download the full 21 GB unless needed.
curl -L https://database.lichess.org/lichess_db_eval.jsonl.zst \
  | zstd -d \
  | .venv/bin/python train/import_lichess_evals.py --limit 120000 \
      -o train/data/lichess_evals_120k.jsonl

.venv/bin/python train/train_kat.py \
  --data train/data/lichess_evals_120k.jsonl \
  --epochs 16 --seed 20260813 \
  --minimum-samples 50000 \
  --output nets/kat_candidate.bin

# Controlled king-relative base: no aggregate threat residual. Do this first.
.venv/bin/python train/train_kat.py \
  --data train/data/nsce_static_games.jsonl --no-threats \
  --target-mode wdl --search-wdl-scale 400 --minimum-samples 50000 \
  --output nets/kat_base_candidate.bin

python3 tools/fastchess_match.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/kat.uci \
  --st 100 --rounds 300 \
  --outdir experiments/$(date +%Y%m%d)_kat
```

Do not silently replace `EvalFile` in `baseline.uci`. Promote only after a paired
fastchess SPRT. `python3 tools/sprt.py` truncates at 60 plies; do not use it for
Elo.

Alternative teacher labels (slower, higher quality):

```bash
.venv/bin/python train/distill.py \
  --teacher /path/to/stockfish --sampler build/nsce \
  --nodes 4000 --positions 50000 --resume \
  -o train/data/sf19_nodes4k.jsonl
```

Millions-scale next step: keep streaming the Lichess dump (≈395M positions) or
HuggingFace `mateuszgrzyb/lichess-stockfish-normalized`, then raise hidden size
only after MAE/SPRT stop moving.

## Fit policy / controller binaries

```bash
bash train/run_train_loop.sh

# Classical LMR telemetry → NSCECTL2 (keep UseSearchController=false while logging).
python3 train/collect_search_telemetry.py --depth 8 --limit 64
.venv/bin/python train/fit_controller.py \
  --telemetry train/data/lmr_telemetry.csv \
  --output nets/controller_fitted.bin
python3 tools/fastchess_match.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/controller_fitted.uci \
  --st 100 --rounds 300 \
  --outdir experiments/$(date +%Y%m%d)_controller
```

## SPRT candidate vs baseline

```bash
python3 tools/fastchess_match.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/trained_nnue.uci \
  --tc 8+0.08 --sprt 0 5 --rounds 3000 \
  --outdir experiments/$(date +%Y%m%d)_eval_sprt
```
