#!/usr/bin/env bash
# Streaming self-play + leaf dump toward a large unlabeled-unfinished corpus.
# Does not stamp game WDL onto hypothetical search leaves. One increment per run;
# raise TARGET_GAMES and re-run. 100M unique leaves is capacity, not this invocation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENGINE="${ENGINE:-$ROOT/build/nsce}"
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
GAMES_FILE="${GAMES_FILE:-$ROOT/train/data/selfplay_colors.jsonl}"
LEAVES_FILE="${LEAVES_FILE:-$ROOT/train/data/leaves_with_results.jsonl}"
TARGET_GAMES="${TARGET_GAMES:-512}"
MOVETIME="${MOVETIME:-100}"
MAX_PLIES="${MAX_PLIES:-200}"
NODES="${NODES:-25000}"
POSITIONS_PER_GAME="${POSITIONS_PER_GAME:-3}"
if [[ -z "${WORKERS:-}" ]]; then
  cpus="$(nproc)"
  WORKERS=$(( cpus > 1 ? cpus - 1 : 1 ))
fi

if [[ ! -x "$ENGINE" ]]; then
  echo "missing engine: $ENGINE" >&2
  exit 1
fi

"$PYTHON" train/selfplay.py \
  --engine "$ENGINE" \
  --config tools/configs/baseline.uci \
  --games "$TARGET_GAMES" \
  --movetime "$MOVETIME" \
  --max-plies "$MAX_PLIES" \
  --both-colors \
  --resume \
  --workers "$WORKERS" \
  -o "$GAMES_FILE"

"$PYTHON" train/collect_leaves.py \
  --engine "$ENGINE" \
  --config tools/configs/baseline.uci \
  --games "$GAMES_FILE" \
  --limit 0 \
  --positions-per-game "$POSITIONS_PER_GAME" \
  --nodes "$NODES" \
  --append \
  --workers "$WORKERS" \
  --output "$LEAVES_FILE"
