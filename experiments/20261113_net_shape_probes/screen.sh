#!/usr/bin/env bash
# Screen the equal-data probe nets at 100 ms/move, extras off, all on build/nsce.
# The host runs another session's SPSA (11 workers), so concurrency stays low;
# both sides of every game share the same load.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
D=experiments/20261113_net_shape_probes
C=train/candidates
match() {  # name-a cfg-a name-b cfg-b
  python3 tools/fastchess_match.py --engine build/nsce --cfg-a "$2" --cfg-b "$4" \
    --name-a "$1" --name-b "$3" --st 100 --rounds "${ROUNDS:-100}" --concurrency "${CONC:-3}" \
    --seed 20261113 --outdir "$D/screen_$1_vs_$3"
}
match s1024 $C/nsceper1_probe_s1024_extras_off.uci hl $C/nsceper1_probe_hl_extras_off.uci
match s1024 $C/nsceper1_probe_s1024_extras_off.uci s512 $C/nsceper1_probe_s512_extras_off.uci
match s1024 $C/nsceper1_probe_s1024_extras_off.uci base768 tools/configs/baseline.uci
echo "$(date -Is) screens done"
