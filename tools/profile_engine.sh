#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${BUILD_DIR:-$ROOT/build-prof}"
CPU="${CPU:-0}"
DEPTH="${DEPTH:-11}"
REPETITIONS="${REPETITIONS:-5}"
OUTDIR="${OUTDIR:-$ROOT/experiments/profiles}"

cmake -S "$ROOT" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_CXX_FLAGS_RELWITHDEBINFO="-O3 -g -fno-omit-frame-pointer" \
  -DNSCE_LTO=OFF -DNSCE_STATS=ON
cmake --build "$BUILD" --parallel 2

if ! command -v perf >/dev/null 2>&1; then
  echo "perf is not installed; benchmark binary is ready at $BUILD/nsce_bench" >&2
  exit 1
fi

mkdir -p "$OUTDIR"
EVENTS="cycles,instructions,branches,branch-misses,cache-references,cache-misses"

echo "== Single-thread search suite =="
taskset -c "$CPU" perf stat -r "$REPETITIONS" -e "$EVENTS" \
  "$BUILD/nsce_bench" "$DEPTH" 1 1

echo "== Four-thread search suite =="
perf stat -r "$REPETITIONS" -e "$EVENTS" \
  "$BUILD/nsce_bench" "$DEPTH" 4 1

echo "== Perft move-generation profile =="
taskset -c "$CPU" perf record -q -g --call-graph dwarf \
  -o "$OUTDIR/perft.data" -- "$BUILD/nsce" perft 6

echo "== Full-search profile =="
taskset -c "$CPU" perf record -q -g --call-graph dwarf \
  -o "$OUTDIR/search.data" -- "$BUILD/nsce_bench" "$DEPTH" 1 2

echo "Profiles written to $OUTDIR/{perft,search}.data"
echo "Open with: perf report -i $OUTDIR/search.data"
