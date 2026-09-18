#!/usr/bin/env bash
# One-shot local board vs the promoted baseline. Run from anywhere:
#   ./play.sh
# Then open http://127.0.0.1:8765/  (Ctrl+C to stop).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

ENGINE="${ENGINE:-$ROOT/build/nsce}"
if [[ ! -x "$ENGINE" ]]; then
  echo "Compilando NSCE (falta $ENGINE)..."
  cmake -G "Unix Makefiles" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
  cmake --build build -j"$(nproc)" --target nsce
fi

exec "$ROOT/tools/play.sh" "$@"
