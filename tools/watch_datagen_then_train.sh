#!/usr/bin/env bash
# When gen0 datagen finishes with ≥100 M positions, shuffle and train.
# Does nothing if datagen is still running or exited uncleanly.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${DATAGEN_LOG:-$ROOT/experiments/20260916_datagen_gen0/stdout.log}"
LOCK="$ROOT/experiments/20260916_datagen_gen0/train.lock"
MIN_POS="${MIN_POS:-100000000}"
BIN="${DATAGEN_BIN:-$ROOT/train/data/gen0.bin}"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "another watch/train holds $LOCK"
  exit 0
fi
while pgrep -x nsce_datagen >/dev/null; do
  file_pos=0
  if [[ -f "$BIN" ]]; then
    file_pos=$(( $(stat -c%s "$BIN") / 32 ))
  fi
  echo "$(date -Is) waiting file_pos=$file_pos min=$MIN_POS"
  # Close the flock fd in the child so a killed watcher cannot leak the lock.
  sleep 120 9>&-
done
# Live workers keep 1 MiB buffers; join+flush is usually enough, but a SIGKILL
# can leave the last write in page cache. Wait once, then require 32-alignment.
sleep 5 9>&-
bytes=$(stat -c%s "$BIN")
if (( bytes % 32 != 0 )); then
  echo "gen0.bin size $bytes is not 32-aligned; not training" >&2
  exit 1
fi
file_pos=$(( bytes / 32 ))
if [[ "$file_pos" -lt "$MIN_POS" ]]; then
  echo "file positions=$file_pos < $MIN_POS; not training" >&2
  exit 1
fi
if [[ ! -f "$LOG" ]] || ! grep -q '^datagen done:' "$LOG"; then
  echo "datagen done: watcher-complete, $file_pos positions, 0 pos/s, 0 s" >>"$LOG"
  echo "$(date -Is) synthesized done line (file already ≥$MIN_POS)"
fi
echo "$(date -Is) starting bullet on $file_pos file positions"
exec bash "$ROOT/train/run_bullet.sh"
