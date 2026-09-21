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
bytes=$(stat -c%s "$BIN")
if (( bytes % 32 != 0 )); then
  echo "$BIN size $bytes is not 32-aligned; not training" >&2
  exit 1
fi
file_pos=$(( bytes / 32 ))
MIN_POS="${MIN_POS:-100000000}"
if (( file_pos < MIN_POS )); then
  echo "$BIN has $file_pos positions; need ≥$MIN_POS" >&2
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
if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  echo "GPU not usable (nvidia-smi failed). Do not train without the GTX 1650." >&2
  exit 1
fi
need_bytes=$(( $(stat -c%s "$BIN") * 2 + 2 * 1024 * 1024 * 1024 ))
avail_bytes=$(df -B1 --output=avail "$ROOT" | tail -1 | tr -d ' ')
if (( avail_bytes < need_bytes )); then
  echo "need ${need_bytes} bytes free for shuffle+checkpoints, have ${avail_bytes}" >&2
  exit 1
fi
UTILS="$BULLET/target/release/bullet-utils"
# Cursor sandbox may redirect CARGO_TARGET_DIR into /tmp; keep artifacts in-tree.
export CARGO_TARGET_DIR="$BULLET/target"
if [[ ! -x "$UTILS" ]]; then
  (cd "$BULLET" && CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}" cargo b -r --package bullet-utils)
fi
echo "shuffle $BIN -> $SHUF"
shuf_ok=0
if [[ -s "$SHUF" && $(stat -c%s "$SHUF") -eq $(stat -c%s "$BIN") ]]; then
  echo "checking existing shuffled file ($(stat -c%s "$SHUF") bytes)"
  if "$UTILS" validate --input "$SHUF"; then
    shuf_ok=1
  else
    echo "existing shuffled file failed validate; reshuffling" >&2
    rm -f "$SHUF"
  fi
fi
if [[ "$shuf_ok" != 1 ]]; then
  # 100 M records ≈ 3.2 GB. 4 GiB buffer is one or two passes on 16 GB RAM.
  "$UTILS" shuffle --input "$BIN" --output "$SHUF" --mem-used-mb "${SHUFFLE_MB:-4096}"
  if ! "$UTILS" validate --input "$SHUF"; then
    echo "shuffle produced an invalid file; deleted $SHUF" >&2
    rm -f "$SHUF"
    exit 1
  fi
fi
export NSCE_DATASET="$SHUF"
GRAPH="${NSCE_GRAPH:-mlp}"
if [[ "$GRAPH" == simple ]]; then
  DEFAULT_CKPT="$ROOT/train/bullet_checkpoints_simple"
  TRAIN_SRC="$ROOT/train/bullet_nsce_simple.rs"
else
  DEFAULT_CKPT="$ROOT/train/bullet_checkpoints"
  TRAIN_SRC="$ROOT/train/bullet_nsce.rs"
fi
CKPT_DIR="${NSCE_CHECKPOINT_DIR:-$DEFAULT_CKPT}"
mkdir -p "$CKPT_DIR"
export NSCE_CHECKPOINT_DIR="$CKPT_DIR"
cp -f "$TRAIN_SRC" "$BULLET/examples/nsce.rs"
NSCE_EX="$BULLET/target/release/examples/nsce"
# Checkpoint path in nsce.rs is relative to third_party/bullet cwd.
if [[ ! -x "$NSCE_EX" || "$TRAIN_SRC" -nt "$NSCE_EX" ]]; then
  echo "rebuild CUDA nsce example ($GRAPH)"
  (cd "$BULLET" && CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}" cargo b -r --example nsce --features cuda)
fi
echo "train $NSCE_EX"
TRAIN_LOG="${NSCE_TRAIN_LOG:-$ROOT/experiments/$(date +%Y%m%d)_bullet_gen${NSCE_GEN:-0}.log}"
mkdir -p "$(dirname "$TRAIN_LOG")"
train_tries=0
while true; do
  echo "$(date -Is) train try=$((train_tries + 1)) latest=$(ls -d "$CKPT_DIR"/nsce-* 2>/dev/null | sort -t- -k2 -n | tail -1 || echo none)"
  if (cd "$BULLET" && "$NSCE_EX") 2>&1 | tee -a "$TRAIN_LOG"; then
    break
  fi
  train_tries=$((train_tries + 1))
  if (( train_tries >= ${NSCE_TRAIN_RETRIES:-40} )); then
    echo "train failed $train_tries times; see $TRAIN_LOG" >&2
    exit 1
  fi
  echo "train exited; resume from last optimiser_state in ${NSCE_TRAIN_RETRY_WAIT:-60}s"
  sleep "${NSCE_TRAIN_RETRY_WAIT:-60}"
done

ENGINE="${NSCE_ENGINE:-$ROOT/build-per1/nsce}"
# Datagen is finished when the watcher reaches here. Rebuild the PER1 loader
# used for float-ref, the 100 ms screen, and gen1 self-play. build-per1/nsce_datagen
# is still the 2026-09-16 512-era 1-layer binary while gen0 is writing; a 128/16/32
# packed net will not load in that inode. Reconfigure first: CMakeLists changed
# after that cache was generated (NSCE_TUNE / FetchContent wrap).
if [[ -d "$ROOT/build-per1" ]]; then
  cmake -S "$ROOT" -B "$ROOT/build-per1" -DCMAKE_BUILD_TYPE=Release \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DFETCHCONTENT_UPDATES_DISCONNECTED=ON \
    || echo "warn: cmake reconfigure failed; trying existing makefiles" >&2
  cmake --build "$ROOT/build-per1" -j2 --target nsce --target nsce_datagen
  ENGINE="$ROOT/build-per1/nsce"
elif [[ ! -x "$ENGINE" ]]; then
  echo "missing $ENGINE" >&2
  exit 1
fi
ckpt=$(ls -d "$CKPT_DIR"/nsce-* 2>/dev/null | sort -t- -k2 -n | tail -1 || true)
if [[ -z "$ckpt" || ! -f "$ckpt/quantised.bin" ]]; then
  echo "no quantised.bin under $CKPT_DIR" >&2
  exit 1
fi
GEN="${NSCE_GEN:-0}"
CAND_REL="nets/nsceper1_gen${GEN}.bin"
CAND_NET="$ROOT/$CAND_REL"
CAND_CFG="$ROOT/train/candidates/nsceper1_gen${GEN}.uci"
OFF_CFG="$ROOT/train/candidates/nsceper1_gen${GEN}_extras_off.uci"
BASE_EVAL=$(python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
from eval_contract import parse_uci_options
print(parse_uci_options(Path(sys.argv[1]) / "tools/configs/baseline.uci").get("EvalFile", ""))
PY
)
if [[ "$BASE_EVAL" == "$CAND_REL" ]]; then
  echo "refusing to pack onto the live baseline EvalFile $BASE_EVAL" >&2
  exit 1
fi
echo "pack $ckpt/quantised.bin -> $CAND_NET"
PACK_FLAGS=()
SIZE_FN=expected_size
if [[ "${NSCE_GRAPH:-mlp}" == simple ]]; then
  PACK_FLAGS+=(--simple)
  SIZE_FN=expected_size_simple
fi
python3 "$ROOT/tools/pack_nsceper1.py" --from-quantised "$ckpt/quantised.bin" "${PACK_FLAGS[@]}" -o "$CAND_NET"
got=$(stat -c%s "$CAND_NET")
exp=$(python3 -c "import sys; sys.path.insert(0, '$ROOT/tools'); from pack_nsceper1 import ${SIZE_FN}; print(${SIZE_FN}())")
if [[ "$got" -ne "$exp" ]]; then
  echo "packed $CAND_NET is $got bytes, expected $exp (NSCEPER1 ${NSCE_GRAPH:-mlp})" >&2
  exit 1
fi
# Alias for gen0 / manuals. Never overwrite a promoted baseline path.
if [[ "$BASE_EVAL" != "nets/nsceper1.bin" ]]; then
  cp -f "$CAND_NET" "$ROOT/nets/nsceper1.bin"
fi
python3 "$ROOT/tools/write_per1_uci.py" --eval-file "$CAND_REL" --extras true -o "$CAND_CFG"
python3 "$ROOT/tools/write_per1_uci.py" --eval-file "$CAND_REL" --extras false -o "$OFF_CFG"
python3 "$ROOT/tools/per1_float_ref.py" --net "$CAND_NET" --engine "$ENGINE" --n 10000
echo "float-ref passed."
if [[ -d "$ROOT/build" ]]; then
  cmake --build "$ROOT/build" -j2 --target nsce || echo "warn: could not rebuild build/nsce" >&2
fi

screen_clear_loss() {
  python3 - "$ROOT" "$1" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
from eval_contract import screen_is_clear_loss
sys.exit(0 if screen_is_clear_loss(json.load(open(sys.argv[2]))) else 1)
PY
}

run_screen() {
  local cfg="$1" name="$2" dir="$3" note="$4"
  echo "screen $ENGINE vs baseline 100 ms N=1000 -> $dir ($name)"
  python3 "$ROOT/tools/fastchess_match.py" \
    --engine "$ENGINE" \
    --cfg-b "$cfg" \
    --name-b "$name" \
    --st 100 --rounds 500 --concurrency 14 \
    --outdir "$dir"
  local json
  json=$(ls -t "$dir"/match_*.json 2>/dev/null | head -1 || true)
  if [[ -n "$json" ]]; then
    python3 "$ROOT/tools/append_fastchess_finding.py" --json "$json" --note "$note"
  fi
  [[ -n "$json" ]]
}

json_h1() {
  python3 - "$ROOT" "$1" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
from eval_contract import sprt_is_h1
sys.exit(0 if sprt_is_h1(json.load(open(sys.argv[2]))) else 1)
PY
}

run_sprt() {
  local cfg="$1" name="$2" dir="$3" note="$4"
  echo "SPRT [0,5] 8+0.08 $name -> $dir"
  python3 "$ROOT/tools/fastchess_match.py" \
    --engine "$ENGINE" \
    --cfg-b "$cfg" \
    --name-b "$name" \
    --tc 8+0.08 --sprt 0 5 --rounds 3000 --concurrency 14 \
    --outdir "$dir"
  local json
  json=$(ls -t "$dir"/match_*.json 2>/dev/null | head -1 || true)
  if [[ -n "$json" ]]; then
    python3 "$ROOT/tools/append_fastchess_finding.py" --json "$json" --note "$note"
  fi
  [[ -n "$json" ]]
}

SCREEN_DIR="${NSCE_SCREEN_OUT:-$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${GEN}_screen}"
if [[ -z "${NSCE_SKIP_SCREEN:-}" ]]; then
  run_screen "$CAND_CFG" "nsceper1_gen${GEN}" "$SCREEN_DIR" \
    "NSCEPER1 gen${GEN} 100 ms screen (EvalFile only, extras on). Do not promote without SPRT H1."
  json=$(ls -t "$SCREEN_DIR"/match_*.json 2>/dev/null | head -1 || true)
  sprt_cfg="$CAND_CFG"
  sprt_name="nsceper1_gen${GEN}"
  do_sprt=0
  if [[ -n "$json" ]] && screen_clear_loss "$json"; then
    echo "extras-on screen is a clear loss; measuring UseExtras=false (do not assume extras can drop)."
    OFF_DIR="${NSCE_EXTRAS_OFF_OUT:-$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${GEN}_extras_off_screen}"
    run_screen "$OFF_CFG" "nsceper1_gen${GEN}_extras_off" "$OFF_DIR" \
      "NSCEPER1 gen${GEN} extras-off 100 ms screen after extras-on clear loss. Do not promote without SPRT H1."
    off_json=$(ls -t "$OFF_DIR"/match_*.json 2>/dev/null | head -1 || true)
    if [[ -n "$off_json" ]] && ! screen_clear_loss "$off_json"; then
      sprt_cfg="$OFF_CFG"
      sprt_name="nsceper1_gen${GEN}_extras_off"
      do_sprt=1
    else
      echo "both 100 ms screens are clear losses; skip SPRT."
    fi
  elif [[ -n "$json" ]]; then
    do_sprt=1
  fi
  if [[ "$do_sprt" == 1 && -z "${NSCE_SKIP_SPRT:-}" ]]; then
    SPRT_DIR="${NSCE_SPRT_OUT:-$ROOT/experiments/$(date +%Y%m%d)_${sprt_name}_sprt}"
    run_sprt "$sprt_cfg" "$sprt_name" "$SPRT_DIR" \
      "NSCEPER1 SPRT [0,5] 8+0.08. Promote only on H1."
    sprt_json=$(ls -t "$SPRT_DIR"/match_*.json 2>/dev/null | head -1 || true)
    if [[ -n "$sprt_json" ]] && json_h1 "$sprt_json"; then
      python3 "$ROOT/tools/promote_eval.py" --sprt "$sprt_json" --manifest "$SPRT_DIR/manifest.json"
      if grep -qiE 'setoption name UseExtras value true' "$sprt_cfg" && [[ -z "${NSCE_SKIP_EXTRAS_OFF:-}" ]]; then
        echo "EvalFile promoted; measuring UseExtras=false against the new baseline."
        AFTER_CFG="$ROOT/train/candidates/nsceper1_gen${GEN}_extras_off_after.uci"
        python3 "$ROOT/tools/write_per1_uci.py" --extras false -o "$AFTER_CFG"
        AFTER_DIR="${NSCE_EXTRAS_OFF_AFTER_OUT:-$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${GEN}_extras_off_after}"
        run_screen "$AFTER_CFG" "nsceper1_gen${GEN}_extras_off" "$AFTER_DIR" \
          "NSCEPER1 extras-off after EvalFile H1. One UseExtras change vs promoted baseline."
        after_json=$(ls -t "$AFTER_DIR"/match_*.json 2>/dev/null | head -1 || true)
        if [[ -n "$after_json" ]] && ! screen_clear_loss "$after_json" && [[ -z "${NSCE_SKIP_SPRT:-}" ]]; then
          AFTER_SPRT="${NSCE_EXTRAS_OFF_SPRT_OUT:-$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${GEN}_extras_off_sprt}"
          run_sprt "$AFTER_CFG" "nsceper1_gen${GEN}_extras_off" "$AFTER_SPRT" \
            "NSCEPER1 extras-off SPRT after EvalFile H1."
          after_sprt_json=$(ls -t "$AFTER_SPRT"/match_*.json 2>/dev/null | head -1 || true)
          if [[ -n "$after_sprt_json" ]] && json_h1 "$after_sprt_json"; then
            python3 "$ROOT/tools/promote_eval.py" --sprt "$after_sprt_json" --manifest "$AFTER_SPRT/manifest.json"
          fi
        fi
      fi
      if [[ -z "${NSCE_SKIP_GEN1:-}" && "${NSCE_GEN:-0}" -lt 2 ]]; then
        next=$(( ${NSCE_GEN:-0} + 1 ))
        echo "starting gen${next} self-play with the promoted net"
        GEN1_OUT="$ROOT/train/data/gen${next}.bin" \
          GEN1_EXP="$ROOT/experiments/$(date +%Y%m%d)_datagen_gen${next}" \
          GEN1_SEED="$next" \
          bash "$ROOT/tools/run_gen1.sh"
        echo "gen${next} datagen done; training that file"
        exec env NSCE_GEN="$next" \
          NSCE_DATASET="$ROOT/train/data/gen${next}.bin" \
          NSCE_SHUFFLED="$ROOT/train/data/gen${next}.shuffled.bin" \
          NSCE_CHECKPOINT_DIR="$ROOT/train/bullet_checkpoints_gen${next}" \
          NSCE_SCREEN_OUT="$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${next}_screen" \
          NSCE_SPRT_OUT="$ROOT/experiments/$(date +%Y%m%d)_nsceper1_gen${next}_sprt" \
          bash "$ROOT/train/run_bullet.sh"
      elif [[ -z "${NSCE_SKIP_SPSA:-}" ]]; then
        echo "last generation H1; preparing SPSA (does not start the infinite tuner loop)"
        bash "$ROOT/tools/run_spsa.sh"
      fi
    else
      echo "SPRT was not H1; baseline.uci unchanged."
    fi
  else
    echo "screen done. SPRT skipped. Manual:"
    echo "  python3 tools/fastchess_match.py --engine $ENGINE --cfg-b $sprt_cfg \\"
    echo "    --name-b $sprt_name --tc 8+0.08 --sprt 0 5 --rounds 3000 \\"
    echo "    --outdir experiments/\$(date +%Y%m%d)_${sprt_name}_sprt"
  fi
else
  echo "NSCE_SKIP_SCREEN set. Screen (do not promote without SPRT H1):"
  echo "  python3 tools/fastchess_match.py --engine $ENGINE --cfg-b $CAND_CFG --st 100 --rounds 500 \\"
  echo "    --outdir experiments/\$(date +%Y%m%d)_nsceper1_gen${GEN}_screen"
fi
