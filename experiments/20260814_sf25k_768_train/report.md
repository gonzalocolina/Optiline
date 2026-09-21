# 768×128 from internal on Stockfish 25k-node labels

Date: 2026-08-14. Teacher: unrestricted Stockfish (`stockfish`),
`Threads=1`, `Hash=16`, `go nodes 25000` on the first 200k FENs of
`train/data/lichess_evals_1m.jsonl`. Labels: `train/data/sf18_nodes25k.jsonl`
(200000 rows, 0 null `score_cp`, sha256 `99c6a7a0…`). Same FENs as the closed
NSCE self-distill; only the teacher changed. Do not compare these MAE numbers
to the NSCE 65.1 cp holdout or the Lichess 114 cp holdout.

Init: `train_nnue.py --init internal`. Output `nets/nnue_sf25k.bin`.
**UseExtras=false** (full eval; extras would fight SF labels). 16 epochs,
batch 256, default lr, seed 20260814. Best float val epoch 16
(MAE 113.08 cp, still falling).

Engine holdout `sha256(fen) % 10 == 0` (N=20039) vs SF 25k-node labels:

| Net | MAE cp | RMSE cp |
| --- | ---: | ---: |
| internal + extras | 143.6 | 216.2 |
| `nnue_sf25k.bin`, extras off | 113.0 | 177.5 |

**+30.5 cp (+21.3%)**. MAE gate passed. Equal-node next, not SPRT.
`baseline.uci` unchanged.
