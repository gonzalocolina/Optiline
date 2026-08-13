#!/usr/bin/env bash
# Full experimental day: ablations → ladder → SPRT controller → report
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/experiments/$(date +%Y%m%d)}"
ENG="$ROOT/build/nsce"
mkdir -p "$OUT"

echo "== Ablation matrix =="
python3 "$ROOT/tools/ablation_match.py" --matrix --outdir "$OUT" --games "${GAMES:-6}" --movetime "${MOVETIME:-80}" --max-plies 40

echo "== Elo ladder =="
python3 "$ROOT/tools/elo_ladder.py" --outdir "$OUT" --games "${LADDER_GAMES:-6}" --movetime "${MOVETIME:-80}"

echo "== SPRT controller vs baseline =="
python3 "$ROOT/tools/sprt.py" --outdir "$OUT" --cfg-a "$ROOT/tools/configs/baseline.uci" \
  --cfg-b "$ROOT/tools/configs/controller.uci" --name-b controller \
  --movetime "${MOVETIME:-80}" --max-games "${SPRT_GAMES:-40}" --max-plies 40

echo "== NNUE latency =="
"$ROOT/build/nsce_bench_nnue" 200000 internal | tee "$OUT/nnue_latency.txt"

echo "Done. See $OUT/report.md"
