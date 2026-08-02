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

# Deterministic random legal trajectories, labeled by a one-thread teacher.
.venv/bin/python train/distill.py \
  --teacher "$(command -v stockfish)" --sampler build/nsce \
  --depth 8 --positions 2000 --seed 20260802 \
  -o train/data/nnue_stockfish_d8.jsonl

.venv/bin/python train/train_nnue.py \
  --data train/data/nnue_stockfish_d8.jsonl \
  --epochs 80 --seed 20260802

.venv/bin/python train/validate_nnue.py \
  --engine build/nsce --data train/data/nnue_stockfish_d8.jsonl
```

`train_nnue.py` trains the exact `768x128x1` topology consumed by C++, uses a
FEN-hash holdout split, augments only the training split by board/color symmetry,
restores the best validation epoch, quantizes to the `NSCENNUE` format and rejects
int16 accumulator overflow. The versioned metrics contain dataset/network SHA-256.

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

## Fit policy / controller binaries

```bash
bash train/run_train_loop.sh
```

## SPRT candidate vs baseline

```bash
python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/trained_nnue.uci \
  --openings tools/openings_balanced.epd \
  --max-games 200
```
