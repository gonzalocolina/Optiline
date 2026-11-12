#!/usr/bin/env bash
# Wait for tools/run_full_corpus.sh to finish, check the corpus against a
# recorded run, then start the confirmatory bullet run on its train partition.
#
#   NSCE_CORPUS_EXP   experiment the running corpus writes (its report.md)
#   NSCE_CORPUS_REF   recorded report whose sha256 lines must match
#                     (default experiments/20261020_datagen_full/report.md)
#   NSCE_CORPUS_DIR   corpus directory (default train/data/full)
#
# Refuses to train when the train/test/source hashes differ from the
# reference: the same seed must give the same corpus on any host.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
EXP="${NSCE_CORPUS_EXP:?set NSCE_CORPUS_EXP to the corpus experiment directory}"
REF="${NSCE_CORPUS_REF:-$ROOT/experiments/20261020_datagen_full/report.md}"
DIR="${NSCE_CORPUS_DIR:-$ROOT/train/data/full}"
STEM="${NSCE_CORPUS_STEM:-gen_seed20261020}"

while pgrep -f "run_validated_datagen.py.*--out-dir $DIR" >/dev/null; do
  pos=0
  [[ -f "$DIR/$STEM.bin" ]] && pos=$(( $(stat -c%s "$DIR/$STEM.bin") / 32 ))
  echo "$(date -Is) corpus running, $pos positions written"
  sleep 600
done

if [[ ! -s "$EXP/report.md" ]]; then
  echo "$EXP/report.md missing: the corpus run did not finish" >&2
  exit 1
fi
hashes() { grep -o -E '(Train|Test|Source)[^`]*sha256 `[0-9a-f]{64}`' "$1" | grep -o -E '[0-9a-f]{64}'; }
if [[ "$(hashes "$EXP/report.md")" != "$(hashes "$REF")" ]]; then
  echo "corpus hashes differ from $REF; not training" >&2
  diff <(hashes "$REF") <(hashes "$EXP/report.md") >&2 || true
  exit 1
fi
echo "$(date -Is) corpus matches $REF byte for byte"

export NSCE_DATASET="$DIR/$STEM.train.bin"
export NSCE_TEST_SET="$DIR/$STEM.test.bin"
export NSCE_REQUIRE_TEST=1
export NSCE_GEN="${NSCE_GEN:-0}"
# A fresh login is needed before the render group applies; sg avoids that.
if [[ -e /dev/kfd && ! -w /dev/kfd ]] && getent group render | grep -qw "$(id -un)"; then
  exec sg render -c "bash '$ROOT/train/run_bullet.sh'"
fi
exec bash "$ROOT/train/run_bullet.sh"
