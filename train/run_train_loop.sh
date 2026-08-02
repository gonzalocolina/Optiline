#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENG="${NSCE:-$ROOT/build/nsce}"
TELEM="${TELEM:-/tmp/nsce_telem_train.csv}"
rm -f "$TELEM"

python3 "$ROOT/train/selfplay.py" --engine "$ENG" --games "${GAMES:-2}" --movetime "${MOVETIME:-40}" \
  --max-plies 40 --config "$ROOT/tools/configs/baseline.uci" -o "$ROOT/train/data/selfplay.jsonl"

printf 'setoption name TelemetryFile value %s\nposition startpos\ngo depth 6\nquit\n' "$TELEM" | "$ENG" >/dev/null

python3 "$ROOT/train/train_from_selfplay.py" \
  --selfplay "$ROOT/train/data/selfplay.jsonl" \
  --telemetry "$TELEM" \
  --policy-out "$ROOT/nets/policy.bin" \
  --controller-out "$ROOT/nets/controller.bin"

python3 "$ROOT/train/distill.py" --depth 6 --positions 8 -o "$ROOT/train/data/distill.jsonl" || true

echo "phase7_train_loop: OK"
