# 768 fine-tune from internal on NSCE 25k-node labels

Date: 2026-08-14. Same dataset as from-scratch
(`train/data/nsce_nodes25k.jsonl`, sha256 `13753581379e…`). Init:
`train_nnue.py --init internal` (HCE default, bit-exact extras-off eval vs
engine). Output `nets/nnue_nsce25k_ft.bin`. Extras on. 16 epochs, lr 0.001,
seed 20260814. Best epoch 6 (RMSE).

Trainer float val MAE **75.1 cp** (from-scratch was 80.9). Later epochs overfit.

Engine holdout N=20039 vs NSCE 25k-node labels:

| Net | MAE cp | RMSE cp |
| --- | ---: | ---: |
| internal + extras | 65.1 | 123.9 |
| `nnue_nsce25k_ft.bin` + extras | 72.3 | 124.1 |
| `nnue_nsce25k.bin` + extras (from scratch) | 84.8 | 133.3 |

**−7.2 cp (−11%) vs internal.** Better than from-scratch, still a MAE gate
fail. No equal-node, no SPRT. `baseline.uci` unchanged.
