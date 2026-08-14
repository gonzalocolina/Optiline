# Training pipeline (Phases 4–7 + lab)

## Self-play with real outcomes

```bash
python3 train/selfplay.py --games 8 --movetime 80 --config tools/configs/baseline.uci
```

Uses UCI `status` (`checkmate` / `stalemate` / `draw` / `ongoing`).

## Trained NNUE (Stockfish distillation)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install numpy

# Deterministic trajectories, labeled by an isolated one-thread teacher.
.venv/bin/python train/distill.py \
  --teacher "$(command -v stockfish)" --sampler build/nsce \
  --depth 8 --positions 2000 --seed 20260802 \
  -o train/data/nnue_stockfish_d8.jsonl

# Optional shallow teacher trajectories retain terminal result metadata.
.venv/bin/python train/distill.py \
  --teacher "$(command -v stockfish)" --sampler build/nsce --self-play \
  --self-play-depth 4 --positions 2000 -o train/data/selfplay.jsonl

.venv/bin/python train/train_nnue.py \
  --data train/data/nnue_stockfish_d8.jsonl \
  --epochs 80 --seed 20260802 --target-mode wdl \
  --wdl-scale 400 --result-weight 0.20 --residualize-extras

# Fine-tune from the frozen HCE default (`--init internal`), a .npz checkpoint,
# or an NSCENNUE .bin instead of random init.

.venv/bin/python train/validate_nnue.py \
  --engine build/nsce --data train/data/nnue_stockfish_d8.jsonl
```

`train_nnue.py` trains the exact `768x128x1` topology consumed by C++. It converts
teacher CP into a canonical WDL/logit search target, optionally blends a recorded
game result, splits by source game/opening group, augments only the training split,
and performs fake integer forward quantization with straight-through gradients by
default. `--no-qat` is available only for diagnostic comparisons. It restores the
best frozen-validation epoch, exports `NSCENNUE`, and rejects conservative int16
accumulator overflow. `--init internal` starts from the frozen HCE default instead
of random weights (also accepts a `.npz` checkpoint or an `NSCENNUE` `.bin`).
Training batches are packed sparse active-feature rows and generate symmetry
variants on demand; `--dense-legacy` is retained only for controlled regression
comparisons.

The bundled network is genuinely optimized from teacher labels, but it is still a
small piece-square network rather than a Stockfish HalfKP/king-bucket architecture.
The current 2k corpus is a reproducible bootstrap, not a claim of Stockfish-level
evaluation quality; promotion still requires a paired game SPRT.

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

## KAT — HalfKA-hm + tactical residual (`NSCEKAT1`)

Better than the 16-bucket HalfKP path at this project's data scale:

- 32 horizontally-mirrored king buckets (king forced onto files e–h)
- Train-time piece-square factorization, folded into the sparse table at export
- 12-dim threat residual (our/their attacked piece counts) — dense, not a sparse explosion
- Labels from Lichess eval DB (centipawns) or Stockfish teacher search; no GPL nets
- WDL/logit targets and fake integer forward are enabled by default; use
  `--target-mode cp` only for an explicitly registered legacy comparison.

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

# Controlled king-relative base: no aggregate threat residual.
.venv/bin/python train/train_kat.py \
  --data train/data/lichess_evals_120k.jsonl --no-threats \
  --target-mode wdl --minimum-samples 50000 \
  --output nets/kat_base_candidate.bin

python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/kat.uci \
  --openings tools/openings_balanced.epd \
  --max-games 200
```

Do not silently replace `EvalFile=internal`. Promote only after a paired SPRT.

Alternative teacher labels (slower, higher quality):

```bash
.venv/bin/python train/distill.py \
  --teacher /path/to/stockfish --sampler build/nsce \
  --nodes 4000 --positions 50000 --resume \
  -o train/data/sf18_nodes4k.jsonl
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
python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/controller_fitted.uci \
  --openings tools/openings_balanced.epd \
  --max-games 200
```

## SPRT candidate vs baseline

```bash
python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/trained_nnue.uci \
  --openings tools/openings_balanced.epd \
  --max-games 200
```
