#!/usr/bin/env bash
# Unpack the on-disk CUDA 12.2 local debs into third_party/cuda-12.2 (no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${CUDA_LOCAL_REPO:-/var/cuda-repo-ubuntu2204-12-2-local}"
DEST="$ROOT/third_party/cuda-12.2"
mkdir -p "$DEST"
debs=(
  cuda-cccl-12-2
  cuda-crt-12-2
  cuda-nvvm-12-2
  cuda-nvcc-12-2
  cuda-cudart-12-2
  cuda-cudart-dev-12-2
  cuda-driver-dev-12-2
  cuda-nvrtc-12-2
  cuda-nvrtc-dev-12-2
  libcublas-12-2
  libcublas-dev-12-2
)
for name in "${debs[@]}"; do
  deb=$(ls "$REPO"/${name}_*.deb 2>/dev/null | head -1 || true)
  if [[ -z "$deb" ]]; then
    echo "missing $name in $REPO" >&2
    exit 1
  fi
  echo "extract $deb"
  dpkg-deb -x "$deb" "$DEST"
done
# NVIDIA packages mix /usr/local/cuda-12.2 and /usr/lib/x86_64-linux-gnu.
CUDA_HOME=""
for cand in "$DEST/usr/local/cuda-12.2" "$DEST/usr/local/cuda"; do
  if [[ -x "$cand/bin/nvcc" ]]; then
    CUDA_HOME=$cand
    break
  fi
done
if [[ -z "$CUDA_HOME" ]]; then
  echo "nvcc not found after extract" >&2
  find "$DEST" -name nvcc | head
  exit 1
fi
mkdir -p "$CUDA_HOME/lib64"
# libcublas / libcudart often land in /usr/lib/x86_64-linux-gnu
if [[ -d "$DEST/usr/lib/x86_64-linux-gnu" ]]; then
  shopt -s nullglob
  for so in "$DEST/usr/lib/x86_64-linux-gnu"/lib{cudart,nvrtc,cublas,cuda}*; do
    ln -sfn "$so" "$CUDA_HOME/lib64/$(basename "$so")"
  done
fi
echo "CUDA_HOME=$CUDA_HOME"
"$CUDA_HOME/bin/nvcc" --version | tail -1
echo "export CUDA_PATH=$CUDA_HOME"
echo "export PATH=$CUDA_HOME/bin:\$PATH"
echo "export LD_LIBRARY_PATH=$CUDA_HOME/lib64:\$LD_LIBRARY_PATH"
