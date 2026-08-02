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

## Fit policy / controller binaries

```bash
bash train/run_train_loop.sh
```

## SPRT candidate vs baseline

```bash
python3 tools/sprt.py --cfg-a tools/configs/baseline.uci --cfg-b tools/configs/controller.uci --max-games 100
```
