#!/usr/bin/env bash
# s1024 again on the same data and position count, with 30% game result in the target.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXP="$ROOT/experiments/20261113_net_shape_probes"
PACKS="$ROOT/train/data/sfbinpack/test80-2024-01-jan-2tb7p.min-v2.v6.binpack,$ROOT/train/data/sfbinpack/test80-2024-02-feb-2tb7p.min-v2.v6.binpack"
env NSCE_BINPACKS="$PACKS" NSCE_SUPERBATCHES=6 NSCE_SAVE_RATE=6 NSCE_THREADS=4 \
  NSCE_GRAPH=simple NSCE_FT=1024 NSCE_WDL=0.3 NSCE_RUN=probe_s1024_wdl30 NSCE_EXP_DIR="$EXP/probe_s1024_wdl30" \
  bash "$ROOT/train/run_bullet_binpack.sh"
