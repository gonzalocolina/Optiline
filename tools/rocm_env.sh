# Source from repo scripts. ROCm/HIP environment for bullet on an AMD GPU.
#
# Debian packages ROCm under /usr instead of /opt/rocm, and ROCm 5.x ships the
# hiprtc symbols inside libamdhip64 rather than a separate libhiprtc. bullet's
# build.rs links amdhip64, hipblas, hiprtc and rocblas from $HIP_PATH/lib, so
# when no real ROCm tree is installed this builds a small shim directory under
# third_party/rocm-shim that points at the system libraries.
_NSCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${HIP_PATH:-}" ]]; then
  if [[ -d /opt/rocm/lib && -e /opt/rocm/lib/libhiprtc.so ]]; then
    export HIP_PATH=/opt/rocm
  else
    _shim="$_NSCE_ROOT/third_party/rocm-shim"
    _sys=/usr/lib/x86_64-linux-gnu
    mkdir -p "$_shim/lib"
    ln -sfn /usr/include "$_shim/include"
    for _l in amdhip64 hipblas rocblas; do
      [[ -e "$_sys/lib$_l.so" ]] && ln -sfn "$_sys/lib$_l.so" "$_shim/lib/lib$_l.so"
    done
    if [[ -e "$_sys/libhiprtc.so" ]]; then
      ln -sfn "$_sys/libhiprtc.so" "$_shim/lib/libhiprtc.so"
    else
      ln -sfn "$_sys/libamdhip64.so" "$_shim/lib/libhiprtc.so"
    fi
    export HIP_PATH="$_shim"
    unset _shim _sys _l
  fi
fi
export ROCM_PATH="${ROCM_PATH:-$HIP_PATH}"
export LD_LIBRARY_PATH="$HIP_PATH/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Radeon 680M / 660M (Rembrandt, gfx1035) and other RDNA2 iGPUs are not in the
# rocBLAS kernel list; they run the gfx1030 code objects. Override only when
# the agent is one of those and the caller has not set a value.
if [[ -z "${HSA_OVERRIDE_GFX_VERSION:-}" ]] && command -v rocminfo >/dev/null 2>&1; then
  # Capture first so grep -m1 cannot SIGPIPE rocminfo under a caller's pipefail.
  _gfx=$(rocminfo 2>/dev/null || true)
  _gfx=$(grep -o -m1 -E 'gfx103[1-6]' <<<"$_gfx" || true)
  if [[ -n "$_gfx" ]]; then
    export HSA_OVERRIDE_GFX_VERSION=10.3.0
  fi
  unset _gfx
fi
