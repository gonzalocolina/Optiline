#!/usr/bin/env bash
# Second round: UHO openings decided 81% of the s1024/s512 pairs 1-1, so the
# close comparisons go again on balanced openings, at fixed nodes (eval quality,
# load cannot bias it) and at 100 ms (quality minus speed). Then WDL 0.3 vs 0.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
D=experiments/20261113_net_shape_probes
C=train/candidates
BAL=tools/openings_balanced.epd
while systemctl --user is-active -q optiline-screen; do sleep 30; done
match() {  # outdir-suffix name-a cfg-a name-b cfg-b limit...
  local tag=$1; shift
  python3 tools/fastchess_match.py --engine build/nsce --cfg-a "$2" --cfg-b "$4" \
    --name-a "$1" --name-b "$3" --openings $BAL --rounds "${ROUNDS:-150}" --concurrency "${CONC:-3}" \
    --seed 20261114 --outdir "$D/screen_$1_vs_$3_$tag" "${@:5}"
}
match n25k s1024 $C/nsceper1_probe_s1024_extras_off.uci s512 $C/nsceper1_probe_s512_extras_off.uci --nodes 25000
match st100 s1024 $C/nsceper1_probe_s1024_extras_off.uci s512 $C/nsceper1_probe_s512_extras_off.uci --st 100
while systemctl --user is-active -q optiline-probe-wdl; do sleep 30; done
match st100 s1024wdl30 $C/nsceper1_probe_s1024_wdl30_extras_off.uci s1024 $C/nsceper1_probe_s1024_extras_off.uci --st 100
echo "$(date -Is) screens2 done"
