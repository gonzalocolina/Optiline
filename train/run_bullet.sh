#!/usr/bin/env bash
# Shuffle gen0.bin then train the NSCEPER1 example. Does not fake a net.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BIN="${NSCE_DATASET:-$ROOT/train/data/gen0.bin}"
SHUF="${NSCE_SHUFFLED:-$ROOT/train/data/gen0.shuffled.bin}"
BULLET="$ROOT/third_party/bullet"
if [[ ! -s "$BIN" ]]; then
  echo "missing $BIN" >&2
  exit 1
fi
if [[ ! -d "$BULLET" ]]; then
  echo "run bash tools/setup_bullet.sh first" >&2
  exit 1
fi
# shellcheck source=cuda_env.sh
source "$ROOT/tools/cuda_env.sh"
if [[ ! -x "${CUDA_PATH}/bin/nvcc" ]]; then
  echo "nvcc missing. Run bash tools/setup_cuda_local.sh" >&2
  exit 1
fi
UTILS="$BULLET/target/release/bullet-utils"
# Cursor sandbox may redirect CARGO_TARGET_DIR into /tmp; keep artifacts in-tree.
export CARGO_TARGET_DIR="$BULLET/target"
if [[ ! -x "$UTILS" ]]; then
  (cd "$BULLET" && CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" cargo b -r --package bullet-utils)
fi
echo "shuffle $BIN -> $SHUF"
# 100 M records ≈ 3.2 GB. 4 GiB buffer is one or two passes on 16 GB RAM.
"$UTILS" shuffle --input "$BIN" --output "$SHUF" --mem-used-mb "${SHUFFLE_MB:-4096}"
export NSCE_DATASET="$SHUF"
mkdir -p "$ROOT/train/bullet_checkpoints"
cp -f "$ROOT/train/bullet_nsce.rs" "$BULLET/examples/nsce.rs"
NSCE_EX="$BULLET/target/release/examples/nsce"
# Checkpoint path in nsce.rs is relative to third_party/bullet cwd.
if [[ ! -x "$NSCE_EX" || "$ROOT/train/bullet_nsce.rs" -nt "$NSCE_EX" ]]; then
  echo "rebuild CUDA nsce example"
  (cd "$BULLET" && CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}" cargo b -r --example nsce --features cuda)
fi
echo "train $NSCE_EX"
(cd "$BULLET" && "$NSCE_EX")

ENGINE="${NSCE_ENGINE:-$ROOT/build-per1/nsce}"
if [[ ! -x "$ENGINE" ]]; then
  cmake --build "$ROOT/build-per1" -j2 --target nsce
  ENGINE="$ROOT/build-per1/nsce"
fi
ckpt=$(ls -d "$ROOT"/train/bullet_checkpoints/nsce-* 2>/dev/null | sort -t- -k2 -n | tail -1 || true)
if [[ -z "$ckpt" || ! -f "$ckpt/quantised.bin" ]]; then
  echo "no quantised.bin under train/bullet_checkpoints" >&2
  exit 1
fi
echo "pack $ckpt/quantised.bin"
python3 "$ROOT/tools/pack_nsceper1.py" --from-quantised "$ckpt/quantised.bin" -o "$ROOT/nets/nsceper1.bin"
python3 "$ROOT/tools/per1_float_ref.py" --net "$ROOT/nets/nsceper1.bin" --engine "$ENGINE" --n 10000
echo "float-ref passed."
# Datagen is finished when the watcher reaches here. Sync build/nsce with the
# PER1 loader; the 100 ms screen uses the engine that just passed float-ref.
if [[ -d "$ROOT/build" ]]; then
  cmake --build "$ROOT/build" -j2 --target nsce || echo "warn: could not rebuild build/nsce" >&2
fi
SCREEN_DIR="${NSCE_SCREEN_OUT:-$ROOT/experiments/$(date +%Y%m%d)_nsceper1_screen}"
if [[ -z "${NSCE_SKIP_SCREEN:-}" ]]; then
  echo "screen $ENGINE vs baseline 100 ms N=1000 -> $SCREEN_DIR"
  python3 "$ROOT/tools/fastchess_match.py" \
    --engine "$ENGINE" \
    --cfg-b "$ROOT/tools/configs/nsceper1.uci" \
    --name-b nsceper1 \
    --st 100 --rounds 500 --concurrency 14 \
    --outdir "$SCREEN_DIR"
  echo "screen done. SPRT only if the candidate is not a clear loss:"
  echo "  python3 tools/fastchess_match.py --engine $ENGINE --cfg-b tools/configs/nsceper1.uci \\"
  echo "    --tc 8+0.08 --sprt 0 5 --rounds 3000 --outdir experiments/\$(date +%Y%m%d)_nsceper1_sprt"
  json=$(ls "$SCREEN_DIR"/match_*.json 2>/dev/null | head -1 || true)
  if [[ -n "$json" ]]; then
    python3 "$ROOT/tools/append_fastchess_finding.py" --json "$json" \
      --note "NSCEPER1 100 ms screen. Do not promote without SPRT H1."
  fi
else
  echo "NSCE_SKIP_SCREEN set. Screen (do not promote without SPRT H1):"
  echo "  python3 tools/fastchess_match.py --engine $ENGINE --cfg-b tools/configs/nsceper1.uci --st 100 --rounds 500 \\"
  echo "    --outdir experiments/\$(date +%Y%m%d)_nsceper1_screen"
fi
