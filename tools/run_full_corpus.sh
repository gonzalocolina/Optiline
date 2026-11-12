#!/usr/bin/env bash
# Production corpus: 1.25e6 games so the training partition can clear 1e8 positions.
# Does not overwrite train/data/validated/. Does not train.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DATAGEN="${NSCE_DATAGEN:-$ROOT/build-datagen/nsce_datagen}"
if [[ ! -x "$DATAGEN" ]]; then
  echo "missing $DATAGEN" >&2
  exit 1
fi
# The output does not depend on the thread count (test_datagen locks this), so
# THREADS only changes wall time. EXP defaults to the recorded 20261020 run;
# point it at a new directory to reproduce that corpus without overwriting it.
THREADS="${DATAGEN_THREADS:-$(nproc)}"
OUT_DIR="${NSCE_CORPUS_DIR:-$ROOT/train/data/full}"
EXP="${NSCE_CORPUS_EXP:-$ROOT/experiments/20261020_datagen_full}"
mkdir -p "$OUT_DIR" "$EXP"
python3 "$ROOT/tools/run_validated_datagen.py" \
  --datagen "$DATAGEN" \
  --games 1250000 \
  --nodes 5000 \
  --threads "$THREADS" \
  --seed 20261020 \
  --scale-games 0 \
  --fraction 0.05 \
  --min-train-positions 100000000 \
  --out-dir "$OUT_DIR" \
  --manifest "$EXP/manifest.json" \
  --report "$EXP/report.md"
echo "corpus validated; train partition meets 100000000 positions"
