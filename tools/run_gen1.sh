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
  if [[ -x "$ROOT/build-per1/nsce_datagen" ]]; then
    DATAGEN_EXE="$ROOT/build-per1/nsce_datagen"
  elif [[ -x "$ROOT/build/nsce_datagen" ]]; then
    DATAGEN_EXE="$ROOT/build/nsce_datagen"
  else
    echo "missing nsce_datagen" >&2
    exit 1
  fi
fi
OUT="${GEN1_OUT:-$ROOT/train/data/gen1.bin}"
EXP="${GEN1_EXP:-$ROOT/experiments/$(date +%Y%m%d)_datagen_gen1}"
mkdir -p "$(dirname "$OUT")" "$EXP"
cmd=(
  "$DATAGEN_EXE" --out "$OUT" --games "${GEN1_GAMES:-1200000}" --nodes 5000
  --threads "${DATAGEN_THREADS:-14}" --eval-file "$NET" --seed "${GEN1_SEED:-1}"
)
if grep -qiE 'setoption name UseExtras value false' "$BASE"; then
  cmd+=(--no-extras)
fi
echo "${cmd[*]}" | tee -a "$EXP/stdout.log"
"${cmd[@]}" >>"$EXP/stdout.log" 2>&1
echo "$(date -Is) gen1 file_pos=$(( $(stat -c%s "$OUT") / 32 ))" | tee -a "$EXP/stdout.log"
