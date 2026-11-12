# ROCm smoke — NSCEPER1 512/32/32 MLP on a Radeon 680M

Date: 2026-11-12. First bullet run on the AMD host. No net from this run is a
candidate; it checks that the training path works and measures its speed.

## Host

| | |
| --- | --- |
| CPU | AMD Ryzen 5 6600H, 6 cores / 12 threads, AVX2 + BMI2 |
| GPU | Radeon 680M (Rembrandt iGPU, `gfx1035`), 1 GiB carve-out + GTT from system RAM |
| RAM | 14 GiB usable, shared with the GPU |
| OS | Debian 13, kernel 6.12, ROCm 5.7.1 from Debian (`hipcc`, `libhipblas-dev` 5.5.1, `librocblas-dev` 5.5.1) |
| Bullet | `jw1912/bullet` 5d70177 (2026-11-05), `--features rocm`, graph `train/bullet_nsce.rs` |

Debian's rocBLAS has no `gfx1035` code objects. `tools/rocm_env.sh` sets
`HSA_OVERRIDE_GFX_VERSION=10.3.0` for RDNA2 iGPUs so the `gfx1030` kernels run,
and builds a `HIP_PATH` shim because ROCm 5.x keeps hiprtc inside `libamdhip64`.

## Throughput

400 batches × 8192 on `train/data/validated/gen_seed20261020.train.bin`,
`NSCE_THREADS=4`, while 11-thread datagen ran on the CPU.

| Setting | Running loss | pos/s |
| --- | ---: | ---: |
| `HSA_OVERRIDE_GFX_VERSION=10.3.0` | 0.028539 | **176 162** |
| no override | 0.028539 | 156 227 |

GPU busy was 100% for the whole run, so the GPU is the limit, not the loader.
The GTX 1650 smoke measured ~450k pos/s ([report](../20260918_bullet_mlp_smoke/report.md),
two batches only). The default schedule, 320 superbatches × 12 208 batches × 8192
(~3.2e10 positions), is about 52 h on this GPU.

## Full script path

`train/run_bullet.sh` with `NSCE_SMOKE=1`, `MIN_POS=0`, `NSCE_REQUIRE_TEST=1`
and the screen, SPRT, extras pair, gen1 and SPSA steps skipped:
backend detected as `rocm`, shuffle + validate, train manifest, ROCm rebuild,
train, pack (1 085 512 bytes, size check passed), float reference against
`build-per1/nsce`:

```text
n=10000 skipped=61 max|int-C++|=0 mismatches=0 max|float-C++|=6.4818 gate=8.0
```

`train/data/lichess_evals_1m.jsonl` (the float-ref FENs) was re-imported from the
current Lichess eval dump with `train/import_lichess_evals.py --limit 1000000`.

## Datagen on this host

The 1200-game validated corpus regenerated with 12 threads gives the same
train, test and source sha256 as
[20261020_datagen_validated](../20261020_datagen_validated/report.md), at
2588 positions/s against 1593 on the previous 4-thread host.
