#!/usr/bin/env bash
# Install bullet (gitignored) and register the NSCE dual-perspective example.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p third_party
if [[ ! -d third_party/bullet/.git ]]; then
  git clone --depth 1 https://github.com/jw1912/bullet third_party/bullet
fi
cp -f train/bullet_nsce.rs third_party/bullet/examples/nsce.rs
TOML=third_party/bullet/crates/bullet_lib/Cargo.toml
if ! grep -q 'name = "nsce"' "$TOML"; then
  printf '\n[[example]]\nname = "nsce"\npath = "../../examples/nsce.rs"\n' >> "$TOML"
fi
# Same HL graph fed from Stockfish-format binpacks (train/data/sfbinpack).
cp -f train/bullet_nsce_hl_binpack.rs third_party/bullet/examples/nsce_binpack.rs
if ! grep -q 'name = "nsce_binpack"' "$TOML"; then
  printf '\n[[example]]\nname = "nsce_binpack"\npath = "../../examples/nsce_binpack.rs"\n' >> "$TOML"
fi
echo "bullet ready. Train after shuffle (cwd is third_party/bullet):"
echo "  (cd third_party/bullet && cargo r -r --example nsce --features cuda)   # NVIDIA"
echo "  (source tools/rocm_env.sh; cd third_party/bullet && cargo r -r --example nsce --features rocm)   # AMD"
echo "  train/run_bullet.sh picks the backend itself (NSCE_GPU_BACKEND=cuda|rocm to force one)."
echo "  dataset default: ../../train/data/gen0.bin  (override with NSCE_DATASET)"
