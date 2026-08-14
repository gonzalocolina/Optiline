# 768×128 from-scratch on NSCE 25k-node labels

Date: 2026-08-14. Dataset `train/data/nsce_nodes25k.jsonl` (200k, sha256
`13753581379e…`). Net `nets/nnue_nsce25k.bin`. Extras on. Seed 20260814,
16 epochs.

Trainer float val MAE 95.4 → 80.9 cp. Engine holdout (N=20039):

- internal + extras: **65.1 cp** MAE
- candidate + extras: **84.8 cp** MAE (−30%)

Gate fail. No 500k, no equal-node, no SPRT. Full write-up:
[20260814_nsce25k_kat_nodes](../20260814_nsce25k_kat_nodes/report.md).
