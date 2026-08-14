#!/usr/bin/env bash
# Step 1 of docs/eval_pipeline.md: clone the frozen arbiter with the same 768×128 net.
# Default EPOCHS=0 re-exports internal through the trainer quantizer (measured PASS).
# Color-flip augmentation is not a ReLU symmetry; clone training uses --augment none.
# Horizontal mirror is the trainer default for later WDL runs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENGINE="${ENGINE:-$ROOT/build/nsce}"
POSITIONS="${POSITIONS:-20000}"
LIMIT="${LIMIT:-64}"
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

if [[ ! -x "$ENGINE" ]]; then
  echo "missing engine: $ENGINE" >&2
  exit 1
fi

"$PYTHON" train/collect_leaves.py \
  --engine "$ENGINE" \
  --config tools/configs/baseline.uci \
  --limit "$LIMIT" \
  --nodes 25000 \
  --output train/data/leaves.jsonl

"$PYTHON" train/distill.py \
  --teacher "$ENGINE" \
  --teacher-config tools/configs/baseline.uci \
  --label static \
  --fens train/data/leaves.jsonl \
  --leaf-sites q_stand_pat,static,in_check_static \
  --sample-uniform \
  --positions "$POSITIONS" \
  -o train/data/nsce_static_clone.jsonl

"$PYTHON" train/train_nnue.py \
  --data train/data/nsce_static_clone.jsonl \
  --init internal \
  --target-mode cp \
  --residualize-extras \
  --epochs "${EPOCHS:-0}" \
  --learning-rate "${LR:-0.0004}" \
  --augment "${AUGMENT:-none}" \
  --output nets/nnue_clone_export.bin \
  --metrics nets/nnue_clone_export.metrics.json

"$PYTHON" train/validate_nnue.py \
  --engine "$ENGINE" \
  --data train/data/nsce_static_clone.jsonl \
  --network nets/nnue_clone_export.bin \
  --use-extras \
  --gate clone \
  --output nets/nnue_clone.validation.json

echo
echo "C++ clone filter done. The pipeline is still unproven until:"
echo "  python3 tools/ablation_match.py --cfg-a tools/configs/baseline.uci \\"
echo "    --cfg-b tools/configs/nnue_clone.uci --name-a baseline --name-b clone \\"
echo "    --games 200 --nodes 25000 --seed 20260814 \\"
echo "    --outdir experiments/\$(date +%Y%m%d)_clone_nodes"
echo "  python3 tools/promotion_gate.py --stage clone \\"
echo "    --validation nets/nnue_clone.validation.json \\"
echo "    --equal-node experiments/.../ablation_summary.json \\"
echo "    --manifest experiments/.../manifest.json"
echo "Do not SPRT a richer net until that clone does not lose."
