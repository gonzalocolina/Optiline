# Source from repo scripts. Puts nvcc 12.2 and libcublas on PATH / LD_LIBRARY_PATH.
# shellcheck disable=SC2034
_NSCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CUDA_PATH="${CUDA_PATH:-$_NSCE_ROOT/third_party/cuda-12.2/usr/local/cuda-12.2}"
export PATH="$CUDA_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_PATH/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset _NSCE_ROOT
