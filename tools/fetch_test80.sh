#!/usr/bin/env bash
# Download linrock/test80-<year> Stockfish binpacks into train/data/sfbinpack.
#
#   bash tools/fetch_test80.sh                 # jan feb mar apr
#   bash tools/fetch_test80.sh 01-jan 05-may   # chosen months of 2024
#   bash tools/fetch_test80.sh 2023-12-dec     # a month of linrock/test80-2023
#
# Each .zst is checked against the sha256 the dataset publishes before it is
# decompressed. The decompressed sha256 goes to SHA256SUMS in the same folder,
# so a training manifest can name the exact bytes it read.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${NSCE_BINPACK_DIR:-$ROOT/train/data/sfbinpack}"
VARIANT="${NSCE_BINPACK_VARIANT:-2tb7p.min-v2.v6}"
MONTHS=("$@")
if (( ${#MONTHS[@]} == 0 )); then
  MONTHS=(01-jan 02-feb 03-mar 04-apr)
fi
mkdir -p "$OUT"
cd "$OUT"
# Each run reads the dataset listings afresh.
rm -f .tree.json .tree-*.json
published_sha() {
  python3 - "$1" "$2" <<'PY'
import json, sys
for entry in json.load(open(sys.argv[1])):
    if entry.get("path") == sys.argv[2]:
        print(entry["lfs"]["oid"])
        break
else:
    sys.exit(f"{sys.argv[2]} is not in the dataset listing")
PY
}

for month in "${MONTHS[@]}"; do
  # A bare month (05-may) is 2024; 2023-12-dec names the year too.
  [[ "$month" =~ ^20[0-9]{2}- ]] || month="2024-$month"
  year="${month%%-*}"
  REPO="linrock/test80-$year"
  TREE="$OUT/.tree-$year.json"
  [[ -s "$TREE" ]] || curl -sS -L --retry 5 -o "$TREE" "https://huggingface.co/api/datasets/$REPO/tree/main?recursive=true"
  name="test80-$month-$VARIANT.binpack"
  if [[ -s "$name" ]] && grep -q "  $name\$" SHA256SUMS 2>/dev/null; then
    echo "$(date -Is) $name already present"
    continue
  fi
  want=$(published_sha "$TREE" "$name.zst")
  echo "$(date -Is) fetch $name.zst (sha256 $want)"
  curl -sS -L -C - --retry 20 --retry-delay 10 --retry-all-errors \
    -o "$name.zst" "https://huggingface.co/datasets/$REPO/resolve/main/$name.zst"
  got=$(sha256sum "$name.zst" | cut -d' ' -f1)
  if [[ "$got" != "$want" ]]; then
    echo "$name.zst sha256 is $got, the dataset publishes $want" >&2
    exit 1
  fi
  echo "$(date -Is) decompress $name"
  zstd -d -f --rm -T0 "$name.zst" -o "$name.part"
  mv -f "$name.part" "$name"
  grep -v "  $name\$" SHA256SUMS > SHA256SUMS.tmp 2>/dev/null || true
  sha256sum "$name" >> SHA256SUMS.tmp
  mv -f SHA256SUMS.tmp SHA256SUMS
  echo "$(date -Is) $name $(stat -c%s "$name") bytes"
done
echo "$(date -Is) done"
