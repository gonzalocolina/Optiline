# CUDA smoke — NSCEPER1 128/16/32 MLP

Date: 2026-09-18. Binary `third_party/bullet/target/release/examples/nsce`
rebuilt 11:40 from `train/bullet_nsce.rs` (L1=128, L2=16, L3=32, pairwise
CReLU, Chess768). The 2026-09-16 21:17 binary was the 2048 L1-only graph.

```text
NSCE_SMOKE=1 NSCE_RESUME=0 \
  NSCE_DATASET=train/data/gen0.bin \
  NSCE_CHECKPOINT_DIR=experiments/20260918_bullet_mlp_smoke \
  third_party/bullet/target/release/examples/nsce
```

Read-only on live `gen0.bin` (writer only appends). Fresh checkpoint dir so
the 2048 optimiser_state is never loaded.

| | |
| --- | --- |
| GPU | GTX 1650 sm_75 |
| Batch | 8192 × 2 |
| Positions | 16 384 |
| Running loss | 0.118384 |
| Throughput | **458 650 pos/s** |
| Wall | 8.2 ms train + ~11 s process |

Graph runs. Throughput is the same order as the 512-wide smoke (~448 k).
Do not treat this checkpoint as a net. Full train waits for gen0 ≥100 M.

Packed `nsceper1.bin` 239 944 bytes (`expected_size()` match). Float-ref vs
`build/nsce` on 10k Lichess FENs: quantized Python == C++ (`mismatches=0`,
max |int−C++|=0), 61 illegal-castle FENs skipped. Do not promote this file.
