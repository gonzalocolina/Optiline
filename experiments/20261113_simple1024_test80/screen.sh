#!/usr/bin/env bash
# After the final run: screen the packed net against the promoted baseline,
# the equal-data s1024 probe and the HL probe. 100 ms, balanced openings, extras off.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
D=experiments/20261113_simple1024_test80
C=train/candidates
while systemctl --user is-active -q optiline-train-s1024; do sleep 60; done
[[ -s nets/nsceper1_simple1024_test80.bin ]] || { echo "no packed net" >&2; exit 1; }
match() {  # name-b cfg-b
  python3 tools/fastchess_match.py --engine build/nsce --cfg-a $C/nsceper1_simple1024_test80_extras_off.uci \
    --cfg-b "$2" --name-a final1024 --name-b "$1" --openings tools/openings_balanced.epd \
    --st 100 --rounds "${ROUNDS:-200}" --concurrency "${CONC:-3}" --seed 20261115 --outdir "$D/screen_final1024_vs_$1"
}
match base768 tools/configs/baseline.uci
match probe_s1024 $C/nsceper1_probe_s1024_extras_off.uci
match probe_hl $C/nsceper1_probe_hl_extras_off.uci
echo "$(date -Is) final screens done"
