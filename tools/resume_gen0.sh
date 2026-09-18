#!/usr/bin/env bash
# After a reboot: append gen0 if still <100 M, then start the train watcher.
# Safe to run while datagen is already live (exits). Uses a new seed so games
# are not duplicates of seed 1 / seed 2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXP="$ROOT/experiments/20260916_datagen_gen0"
BIN="${DATAGEN_BIN:-$ROOT/train/data/gen0.bin}"
LOG="${DATAGEN_LOG:-$EXP/stdout.log}"
LOCK="$EXP/datagen.lock"
SEED_FILE="$EXP/next_seed"
MIN_POS="${MIN_POS:-100000000}"
EVAL_FILE="${EVAL_FILE:-$ROOT/nets/nnue_search_leaves40k_rw0.bin}"
THREADS="${DATAGEN_THREADS:-14}"
mkdir -p "$EXP"
exec 8>"$LOCK"
if ! flock -n 8; then
  echo "another resume_gen0 holds $LOCK"
  exit 0
fi
if pgrep -x nsce_datagen >/dev/null; then
  echo "nsce_datagen already running"
  exit 0
fi
if [[ ! -x "$ROOT/build-per1/nsce_datagen" && ! -x "$ROOT/build/nsce_datagen" ]]; then
  echo "missing nsce_datagen" >&2
  exit 1
fi
DATAGEN_EXE="${DATAGEN_EXE:-}"
if [[ -z "$DATAGEN_EXE" ]]; then
  if [[ -x "$ROOT/build-per1/nsce_datagen" ]]; then
    DATAGEN_EXE="$ROOT/build-per1/nsce_datagen"
  else
    DATAGEN_EXE="$ROOT/build/nsce_datagen"
  fi
fi
mkdir -p "$(dirname "$BIN")"
: >>"$BIN"
file_pos=$(( $(stat -c%s "$BIN") / 32 ))
echo "$(date -Is) gen0 records=$file_pos min=$MIN_POS"

start_watcher() {
  if [[ -f "$EXP/watch.pid" ]] && kill -0 "$(cat "$EXP/watch.pid")" 2>/dev/null; then
    echo "watcher already pid $(cat "$EXP/watch.pid")"
    return 0
  fi
  nohup bash "$ROOT/tools/watch_datagen_then_train.sh" >>"$EXP/watch.log" 2>&1 &
  echo $! >"$EXP/watch.pid"
  echo "watcher pid $(cat "$EXP/watch.pid")"
}

if (( file_pos >= MIN_POS )); then
  if ! grep -q '^datagen done:' "$LOG" 2>/dev/null; then
    echo "datagen done: resume-complete, $file_pos positions, 0 pos/s, 0 s" >>"$LOG"
  fi
  start_watcher
  exit 0
fi

need=$(( MIN_POS - file_pos ))
# ~96 positions / game in the seed-1 run; 20k extra games as margin.
games=$(( need / 96 + 20000 ))
if (( games < 1000 )); then games=1000; fi
seed=2
if [[ -f "$SEED_FILE" ]]; then
  seed=$(cat "$SEED_FILE")
fi
echo $(( seed + 1 )) >"$SEED_FILE"
{
  echo
  echo "=== resume_gen0 $(date -Is) seed=$seed games=$games append records=$file_pos ==="
} >>"$LOG"
nohup "$DATAGEN_EXE" --out "$BIN" --games "$games" --nodes 5000 \
  --threads "$THREADS" --eval-file "$EVAL_FILE" --seed "$seed" \
  >>"$LOG" 2>&1 &
echo $! >"$EXP/datagen.pid"
echo "datagen pid $(cat "$EXP/datagen.pid") exe=$DATAGEN_EXE seed=$seed games=$games"
start_watcher
