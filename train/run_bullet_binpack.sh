#!/usr/bin/env bash
# Train an NSCEPER1 net from Stockfish binpacks, pack it, check the export.
# Does not play games and does not promote: screen the packed net with
# tools/fastchess_match.py afterwards.
#
#   NSCE_GRAPH        simple (default): (768→FT)×2 → 1, 8 output buckets
#                     hl: (768→512)×2 → 32 → 1
#   NSCE_FT           accumulator width of the simple graph (default 768)
#   NSCE_BINPACKS     comma separated; default every train/data/sfbinpack/*.binpack
#                     (bash tools/fetch_test80.sh downloads them)
#   NSCE_RUN          run name (default <graph><ft>_binpack)
#   NSCE_SUPERBATCHES, NSCE_LR, NSCE_WDL, NSCE_BATCH, NSCE_THREADS, ...
#                     read by the trainer itself
#
# Writes train/bullet_checkpoints_<run>/, nets/nsceper1_<run>.bin,
# train/candidates/nsceper1_<run>{,_extras_off}.uci and
# experiments/<date>_<run>/{manifest.json,train.log}.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BULLET="$ROOT/third_party/bullet"
[[ -d "$HOME/.cargo/bin" ]] && export PATH="$HOME/.cargo/bin:$PATH"

# A fresh login is needed before the render group applies; sg avoids that.
if [[ -e /dev/kfd && ! -w /dev/kfd && -z "${NSCE_SG_DONE:-}" ]] && getent group render | grep -qw "$(id -un)"; then
  export NSCE_SG_DONE=1
  exec sg render -c "bash '$ROOT/train/run_bullet_binpack.sh'"
fi

GRAPH="${NSCE_GRAPH:-simple}"
if [[ "$GRAPH" == simple ]]; then
  export NSCE_FT="${NSCE_FT:-768}"
  EXAMPLE=nsce_simple_binpack
  TRAIN_SRC="$ROOT/train/bullet_nsce_simple_binpack.rs"
  RUN="${NSCE_RUN:-simple${NSCE_FT}_binpack}"
  PACK_FLAGS=(--simple --buckets 8 --hidden "$NSCE_FT")
elif [[ "$GRAPH" == hl ]]; then
  EXAMPLE=nsce_binpack
  TRAIN_SRC="$ROOT/train/bullet_nsce_hl_binpack.rs"
  RUN="${NSCE_RUN:-hl_binpack}"
  PACK_FLAGS=(--hl)
else
  echo "NSCE_GRAPH must be simple or hl, not $GRAPH" >&2
  exit 1
fi

if [[ -z "${NSCE_BINPACKS:-}" ]]; then
  shopt -s nullglob
  files=("$ROOT"/train/data/sfbinpack/*.binpack)
  shopt -u nullglob
  if (( ${#files[@]} == 0 )); then
    echo "no binpacks under train/data/sfbinpack; run bash tools/fetch_test80.sh" >&2
    exit 1
  fi
  NSCE_BINPACKS=$(IFS=,; echo "${files[*]}")
fi
export NSCE_BINPACKS
IFS=, read -r -a PACKS <<<"$NSCE_BINPACKS"
for f in "${PACKS[@]}"; do
  if [[ ! -s "$f" ]]; then
    echo "missing binpack $f" >&2
    exit 1
  fi
done

# Bullet has no CPU trainer; never fall back.
BACKEND="${NSCE_GPU_BACKEND:-auto}"
rocm_has_gpu() {
  local out
  out=$(rocminfo 2>/dev/null || true)
  grep -q -E 'Name: +gfx' <<<"$out"
}
if [[ "$BACKEND" == auto ]]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    BACKEND=cuda
  elif command -v rocminfo >/dev/null 2>&1 && rocm_has_gpu; then
    BACKEND=rocm
  else
    echo "no usable GPU: nvidia-smi failed and rocminfo lists no gfx agent." >&2
    exit 1
  fi
fi
if [[ "$BACKEND" == cuda ]]; then
  # shellcheck source=../tools/cuda_env.sh
  source "$ROOT/tools/cuda_env.sh"
elif [[ "$BACKEND" == rocm ]]; then
  # shellcheck source=../tools/rocm_env.sh
  source "$ROOT/tools/rocm_env.sh"
else
  echo "NSCE_GPU_BACKEND must be cuda, rocm or auto, not $BACKEND" >&2
  exit 1
fi
echo "GPU backend $BACKEND, graph $GRAPH, run $RUN"

if [[ ! -d "$BULLET" ]] || ! grep -q "name = \"$EXAMPLE\"" "$BULLET/crates/bullet_lib/Cargo.toml"; then
  bash "$ROOT/tools/setup_bullet.sh" >/dev/null
fi
export CARGO_TARGET_DIR="$BULLET/target"
BIN="$BULLET/target/release/examples/$EXAMPLE"
STAMP="$BIN.backend"
cp -f "$TRAIN_SRC" "$BULLET/examples/$EXAMPLE.rs"
if [[ ! -x "$BIN" || "$TRAIN_SRC" -nt "$BIN" || "$(cat "$STAMP" 2>/dev/null)" != "$BACKEND" ]]; then
  echo "rebuild $BACKEND $EXAMPLE"
  (cd "$BULLET" && CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}" cargo b -r --example "$EXAMPLE" --features "$BACKEND")
  echo "$BACKEND" > "$STAMP"
fi

export NSCE_GRAPH_SOURCE="$BULLET/examples/$EXAMPLE.rs"
export NSCE_CHECKPOINT_DIR="${NSCE_CHECKPOINT_DIR:-$ROOT/train/bullet_checkpoints_$RUN}"
EXP="${NSCE_EXP_DIR:-$ROOT/experiments/$(date +%Y%m%d)_$RUN}"
mkdir -p "$NSCE_CHECKPOINT_DIR" "$EXP"
TRAIN_LOG="$EXP/train.log"

python3 - "$ROOT" "$EXP/manifest.json" "$GRAPH" "$RUN" "$TRAIN_SRC" "$BACKEND" "${PACKS[@]}" <<'PY'
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

root, out, graph, run, src, backend, *packs = sys.argv[1:]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def git(*args: str, cwd: str = root) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True).stdout.strip()


data = []
for name in packs:
    path = Path(name)
    known = {}
    sums = path.parent / "SHA256SUMS"
    if sums.is_file():
        for line in sums.read_text().splitlines():
            digest, _, fname = line.partition("  ")
            known[Path(fname).name] = digest
    data.append(
        {
            "path": str(path),
            "bytes": path.stat().st_size,
            # fetch_test80.sh hashed the file when it wrote it.
            "sha256": known.get(path.name) or sha256(path),
        }
    )
manifest = {
    "kind": "bullet_binpack_training",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "run": run,
    "graph": graph,
    "backend": backend,
    "trainer_source": os.path.relpath(src, root),
    "trainer_source_sha256": sha256(Path(src)),
    "bullet_commit": git("rev-parse", "HEAD", cwd=os.path.join(root, "third_party/bullet")),
    "git_commit": git("rev-parse", "HEAD"),
    "git_dirty": bool(git("status", "--porcelain")),
    "hyperparameters": {k: v for k, v in sorted(os.environ.items()) if k.startswith("NSCE_") and k != "NSCE_BINPACKS"},
    "binpacks": data,
}
Path(out).write_text(json.dumps(manifest, indent=2) + "\n")
PY
echo "train manifest $EXP/manifest.json"

tries=0
while true; do
  echo "$(date -Is) train try=$((tries + 1)) latest=$(ls -d "$NSCE_CHECKPOINT_DIR"/nsce-* 2>/dev/null | sort -t- -k2 -n | tail -1 || echo none)" | tee -a "$TRAIN_LOG"
  # Bullet redraws its progress line with carriage returns and colours it;
  # keep whole plain lines.
  if (cd "$BULLET" && "$BIN") 2>&1 | stdbuf -oL tr '\r' '\n' | sed -u 's/\x1b\[[0-9;]*[A-Za-z]//g' \
      | grep --line-buffered -v -E '^\s*$|batches, [0-9]+ pos/sec|Estimated time to end of superbatch' >> "$TRAIN_LOG"; then
    break
  fi
  tries=$((tries + 1))
  if (( tries >= ${NSCE_TRAIN_RETRIES:-20} )); then
    echo "train failed $tries times; see $TRAIN_LOG" >&2
    exit 1
  fi
  echo "$(date -Is) train exited; resume from the last checkpoint in ${NSCE_TRAIN_RETRY_WAIT:-60}s" | tee -a "$TRAIN_LOG"
  sleep "${NSCE_TRAIN_RETRY_WAIT:-60}"
done

ckpt=$(ls -d "$NSCE_CHECKPOINT_DIR"/nsce-* 2>/dev/null | sort -t- -k2 -n | tail -1 || true)
if [[ -z "$ckpt" || ! -f "$ckpt/quantised.bin" ]]; then
  echo "no quantised.bin under $NSCE_CHECKPOINT_DIR" >&2
  exit 1
fi
NET_REL="${NSCE_PACK_REL:-nets/nsceper1_$RUN.bin}"
python3 "$ROOT/tools/pack_nsceper1.py" --from-quantised "$ckpt/quantised.bin" "${PACK_FLAGS[@]}" -o "$ROOT/$NET_REL"
python3 "$ROOT/tools/write_per1_uci.py" --eval-file "$NET_REL" --extras true -o "$ROOT/train/candidates/nsceper1_$RUN.uci"
python3 "$ROOT/tools/write_per1_uci.py" --eval-file "$NET_REL" --extras false -o "$ROOT/train/candidates/nsceper1_${RUN}_extras_off.uci"
ENGINE="${NSCE_ENGINE:-$ROOT/build/nsce}"
python3 "$ROOT/tools/per1_float_ref.py" --net "$ROOT/$NET_REL" --engine "$ENGINE" --n "${NSCE_FLOAT_REF_N:-2000}" | tee -a "$TRAIN_LOG"
echo "$(date -Is) packed $ckpt -> $NET_REL sha256 $(sha256sum "$ROOT/$NET_REL" | cut -d' ' -f1)" | tee -a "$TRAIN_LOG"
