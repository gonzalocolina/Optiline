#!/usr/bin/env bash
# Tablero local contra el baseline promovido.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

ENGINE="${ENGINE:-$ROOT/build/nsce}"
if [[ ! -x "$ENGINE" ]]; then
  echo "missing engine: $ENGINE" >&2
  echo "  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release" >&2
  echo '  cmake --build build -j"$(nproc)"' >&2
  exit 1
fi

echo "Lanzando tablero (no abre el navegador; la URL sale abajo)."
exec "$PYTHON" -u "$ROOT/tools/play.py" --engine "$ENGINE" "$@"
