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
OUT_DIR="$ROOT/train/data/full"
EXP="$ROOT/experiments/20261020_datagen_full"
mkdir -p "$OUT_DIR" "$EXP"
python3 "$ROOT/tools/run_validated_datagen.py" \
  --datagen "$DATAGEN" \
  --games 1250000 \
  --nodes 5000 \
  --threads 4 \
  --seed 20261020 \
  --scale-games 0 \
  --fraction 0.05 \
  --min-train-positions 100000000 \
  --out-dir "$OUT_DIR" \
  --manifest "$EXP/manifest.json" \
  --report "$EXP/report.md"
echo "corpus validated; train partition meets 100000000 positions"
