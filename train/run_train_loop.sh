#!/usr/bin/env bash
# Phase 7 loop: self-play under time budget -> fit nets -> optional reload smoke.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENG="${NSCE:-$ROOT/build/nsce}"
TELEM="${TELEM:-/tmp/nsce_telem_train.csv}"
rm -f "$TELEM"

python3 "$ROOT/train/selfplay.py" --engine "$ENG" --games "${GAMES:-2}" --movetime "${MOVETIME:-30}" \
  --max-plies 24 -o "$ROOT/train/data/selfplay.jsonl"

# Collect a short telemetry sample
printf 'setoption name TelemetryFile value %s\nposition startpos\ngo depth 6\nquit\n' "$TELEM" | "$ENG" >/dev/null

python3 "$ROOT/train/train_from_selfplay.py" \
  --selfplay "$ROOT/train/data/selfplay.jsonl" \
  --telemetry "$TELEM" \
  --policy-out "$ROOT/nets/policy.bin" \
  --controller-out "$ROOT/nets/controller.bin"

printf 'setoption name PolicyFile value %s/nets/policy.bin\nsetoption name ControllerFile value %s/nets/controller.bin\nposition startpos\ngo depth 4\nquit\n' "$ROOT" "$ROOT" | "$ENG" | tail -5
echo "phase7_train_loop: OK"
