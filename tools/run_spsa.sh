#!/usr/bin/env bash
# Weather-factory SPSA after a P1 net exists. Does not hand-tune constants.
# Requires: nets/nsceper1.bin, build/nsce-tune (CMake -DNSCE_TUNE=ON), fastchess.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENGINE="${NSCE_TUNE_ENGINE:-$ROOT/build/nsce-tune}"
NET="${NSCEPER1:-}"
if [[ -z "$NET" ]]; then
  NET=$(python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "tools"))
from eval_contract import net_kind, parse_uci_options, resolve_eval_file
root = Path(sys.argv[1])
eval_file = parse_uci_options(root / "tools/configs/baseline.uci").get("EvalFile", "")
if net_kind(eval_file, root) != "per1":
    raise SystemExit("baseline EvalFile is not NSCEPER1 — do not SPSA until a P1 net is promoted")
path = resolve_eval_file(root, eval_file)
if path is None or not path.is_file():
    raise SystemExit(f"missing promoted EvalFile {eval_file}")
print(path)
PY
)
fi
if [[ ! -s "$NET" ]]; then
  echo "no P1 net at $NET — do not SPSA until gen0 trains and packs" >&2
  exit 1
fi
if [[ ! -x "$ENGINE" ]]; then
  echo "missing $ENGINE. Build with: cmake -S . -B build-tune -DNSCE_TUNE=ON -DCMAKE_BUILD_TYPE=Release && cmake --build build-tune -j --target nsce && cp build-tune/nsce $ENGINE" >&2
  exit 1
fi
WF="$ROOT/third_party/weather-factory"
if [[ ! -f "$WF/main.py" ]]; then
  echo "missing weather-factory (gitignored). Clone https://github.com/jw1912/weather-factory $WF" >&2
  exit 1
fi
TUNER="$WF/tuner"
mkdir -p "$TUNER"
cp -f "$ENGINE" "$TUNER/engine"
cp -f "$ROOT/tools/openings_uho.epd" "$TUNER/book.epd"
cp -f "$ROOT/tools/configs/spsa.json" "$WF/config.json"
cat >"$WF/cutechess.json" <<EOF
{
  "engine": "engine",
  "book": "book.epd",
  "games": 16,
  "tc": 8,
  "hash": 16,
  "threads": 8,
  "save_rate": 10,
  "pgnout": "tuner/games.pgn",
  "use_fastchess": true
}
EOF
# A ≈ 30k games / 10. weather-factory reads config.json (copied above).
python3 - <<'PY'
import json
from pathlib import Path
p = Path("third_party/weather-factory/config.json")
cfg = json.loads(p.read_text())
cfg["A"] = 3000
p.write_text(json.dumps(cfg, indent=4) + "\n")
PY
ln -sfn "$ROOT/third_party/fastchess/fastchess" "$TUNER/fastchess"
python3 - "$ROOT" "$NET" "$WF/cutechess.py" "$WF/cutechess.json" <<'PY'
import json
import sys
from pathlib import Path

root, net, src, cfg_path = map(Path, sys.argv[1:5])
sys.path.insert(0, str(root / "tools"))
from eval_contract import net_kind, parse_uci_options, truthy

text = src.read_text()
if "extra_uci" not in text:
    text = text.replace(
        "        use_fastchess: bool = True\n    ):",
        "        use_fastchess: bool = True,\n        extra_uci: str = \"\"\n    ):",
    )
    text = text.replace(
        "        self.use_fastchess = use_fastchess\n",
        "        self.use_fastchess = use_fastchess\n        self.extra_uci = extra_uci.strip()\n",
    )
    text = text.replace(
        'f"option.Hash={self.hash_size} {\' \'.join(params_a)} "',
        'f"option.Hash={self.hash_size} {self.extra_uci} {\' \'.join(params_a)} "',
    )
    text = text.replace(
        'f"option.Hash={self.hash_size} {\' \'.join(params_b)} "',
        'f"option.Hash={self.hash_size} {self.extra_uci} {\' \'.join(params_b)} "',
    )
    if "extra_uci" not in text:
        raise SystemExit("failed to patch weather-factory cutechess.py for EvalFile")
    src.write_text(text)

base = parse_uci_options(root / "tools/configs/baseline.uci")
if net_kind(base.get("EvalFile", ""), root) != "per1":
    raise SystemExit("SPSA extra_uci requires a promoted PER1 EvalFile")
flag = "true" if truthy(base.get("UseExtras", "true")) else "false"
extra = (
    f"option.EvalFile={net.resolve()} option.Threads=1 "
    f"option.UseNNUE=true option.UseExtras={flag}"
)
cfg = json.loads(cfg_path.read_text())
cfg["extra_uci"] = extra
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print("SPSA extra_uci", extra)
PY
echo "SPSA ready in $WF (8+0.08, UHO book, 8 concurrent, EvalFile=$NET). Run:"
echo "  (cd $WF && python3 main.py)"
echo "Do not start this while datagen or a timed KPI is using the machine."
