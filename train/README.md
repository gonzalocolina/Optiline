# Training pipeline (Phases 4–7 + lab)

Evaluator manufacture is ordered. Do not skip to KAT, Stockfish labels, or a
wider net until the frozen 768 arbiter can be cloned. Canonical protocol:
[docs/eval_pipeline.md](../docs/eval_pipeline.md).

## 1. Clone the frozen arbiter (required first)

Static C++ eval (internal net + extras), same `768×128`, quantized binary must
reproduce those notes and not lose equal-node N≥200.

```bash
bash train/run_clone_arbiter.sh
```

`--label static` is `eval details`, not `go nodes`. `--residualize-extras` is
mandatory on the 768 path because runtime adds extras(). Teacher cp is converted
with `--teacher-wdl-scale` (that teacher) into `--search-wdl-scale` (NSCE search
coin). Clone uses `--target-mode cp` because the teacher already is NSCE.

## Self-play with real outcomes

```bash
python3 train/selfplay.py --games 8 --movetime 80 --both-colors \
  --config tools/configs/baseline.uci \
  --positions-out train/data/selfplay_positions.jsonl
```

Uses UCI `status` (`checkmate` / `stalemate` / `draw` / `ongoing`). A `max_plies`
cutoff is **not** a draw: those positions are written without `result` so WDL mix
does not treat an aborted game as 1/2-1/2. Path FENs from those games were
equal-node coin flips. Stamp a finished-game result onto search leaves instead:

```bash
python3 train/collect_leaves.py --games train/data/selfplay_colors.jsonl \
  --limit 0 --positions-per-game 3 --nodes 25000 \
  --output train/data/leaves_with_results.jsonl
```

Prefer balanced openings, not random walks and not the first slice of a dump.
Default `--max-plies` is 200.

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
equal-node N≥200 clearly above 0.5, then equal-time SPRT, one change, extras
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

Illegal until the 768 clone (and then a winning 768) has passed
[docs/eval_pipeline.md](../docs/eval_pipeline.md) steps 1–7. The first richer net
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
