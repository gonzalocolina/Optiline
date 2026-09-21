#!/usr/bin/env bash
# Gen1+ self-play after SPRT H1 promoted a PER1 EvalFile.
# Runs in the foreground so the caller can shuffle+train the new file.
# Uses whatever EvalFile baseline.uci currently names — not a hardcoded alias.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE="$ROOT/tools/configs/baseline.uci"
NET="${NSCEPER1:-}"
if [[ -z "$NET" ]]; then
  NET=$(python3 - "$ROOT" "$BASE" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
from eval_contract import net_kind, parse_uci_options, resolve_eval_file
root = Path(sys.argv[1])
options = parse_uci_options(Path(sys.argv[2]))
eval_file = options.get("EvalFile", "")
if net_kind(eval_file, root) != "per1":
    raise SystemExit("baseline EvalFile is not NSCEPER1 — promote only after SPRT H1")
path = resolve_eval_file(root, eval_file)
if path is None or not path.is_file():
    raise SystemExit(f"missing promoted EvalFile {eval_file}")
print(path)
PY
)
fi
if [[ ! -s "$NET" ]]; then
  echo "no $NET — do not gen1 before a packed P1 net" >&2
  exit 1
fi
if pgrep -x nsce_datagen >/dev/null; then
  echo "nsce_datagen already running" >&2
  exit 1
fi
DATAGEN_EXE="${DATAGEN_EXE:-}"
if [[ -z "$DATAGEN_EXE" ]]; then
  if [[ -d "$ROOT/build-per1" ]]; then
    DATAGEN_EXE="$ROOT/build-per1/nsce_datagen"
  elif [[ -d "$ROOT/build" ]]; then
    DATAGEN_EXE="$ROOT/build/nsce_datagen"
  fi
fi
if [[ -z "$DATAGEN_EXE" ]]; then
  echo "missing nsce_datagen" >&2
  exit 1
fi
# The live gen0 writer is the 2026-09-16 512-era binary. Rebuild so gen1 can
# load the promoted 128/16/32 NSCEPER1 (safe: this script refuses a live writer).
build_dir=$(dirname "$DATAGEN_EXE")
if [[ -d "$build_dir" && -f "$build_dir/CMakeCache.txt" ]]; then
  cmake -S "$ROOT" -B "$build_dir" \
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
    -DFETCHCONTENT_UPDATES_DISCONNECTED=ON \
    || echo "warn: cmake reconfigure failed; trying existing makefiles" >&2
  cmake --build "$build_dir" -j2 --target nsce_datagen
fi
if [[ ! -x "$DATAGEN_EXE" ]]; then
  echo "missing $DATAGEN_EXE after rebuild" >&2
  exit 1
fi
OUT="${GEN1_OUT:-$ROOT/train/data/gen1.bin}"
EXP="${GEN1_EXP:-$ROOT/experiments/$(date +%Y%m%d)_datagen_gen1}"
MIN_POS="${MIN_POS:-100000000}"
mkdir -p "$(dirname "$OUT")" "$EXP"
if [[ -e "$OUT" ]]; then
  exist_bytes=$(stat -c%s "$OUT")
  if (( exist_bytes % 32 != 0 )); then
    echo "refusing to append to unaligned $OUT ($exist_bytes bytes)" >&2
    exit 1
  fi
fi
seed="${GEN1_SEED:-1}"
games="${GEN1_GAMES:-1200000}"
no_extras=0
if grep -qiE 'setoption name UseExtras value false' "$BASE"; then
  no_extras=1
fi
while true; do
  cmd=(
    "$DATAGEN_EXE" --out "$OUT" --games "$games" --nodes 5000
    --threads "${DATAGEN_THREADS:-14}" --eval-file "$NET" --seed "$seed"
  )
  if [[ "$no_extras" == 1 ]]; then
    cmd+=(--no-extras)
  fi
  echo "${cmd[*]}" | tee -a "$EXP/stdout.log"
  "${cmd[@]}" >>"$EXP/stdout.log" 2>&1
  bytes=$(stat -c%s "$OUT")
  if (( bytes % 32 != 0 )); then
    echo "$OUT size $bytes is not 32-aligned" >&2
    exit 1
  fi
  file_pos=$(( bytes / 32 ))
  echo "$(date -Is) gen1 file_pos=$file_pos min=$MIN_POS" | tee -a "$EXP/stdout.log"
  if (( file_pos >= MIN_POS )); then
    break
  fi
  need=$(( MIN_POS - file_pos ))
  games=$(( need / 96 + 50000 ))
  if (( games < 1000 )); then games=1000; fi
  seed=$(( seed + 1 ))
  echo "$(date -Is) gen1 short; appending seed=$seed games=$games" | tee -a "$EXP/stdout.log"
done
