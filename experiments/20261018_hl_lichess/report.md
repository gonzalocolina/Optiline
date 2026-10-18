# HL net trained on the Lichess evaluation database

Same graph as the September HL net: `(768→512)×2` SCReLU → 32 SCReLU → 1. New labels.

## Dataset

The public source is the [Lichess evaluation database](https://database.lichess.org/lichess_db_eval.jsonl.zst), CC0. The file served on 18 Oct 2026 is 22 423 777 007 bytes, last-modified 2 Oct 2026, and the site lists 416 442 401 Stockfish-evaluated positions. Each row is a FEN plus one or more searches. There is no game result.

`tools/lichess_to_bullet.py` streams that dump and packs bulletformat `ChessBoard` records (32 bytes, the layout in `engine/src/datagen.cpp`). This run kept the first 2 000 000 positions with depth ≥ 12 and |cp| ≤ 3000, dropped mates and duplicate placements, and shuffled with seed 20261018. Another 2 000 positions were held out. File `train/data/lichess_eval_2m.bin`, SHA-256 `075ec5e26c55e247a260d197125d1d172ba0bc0897c97c541043a3f151cbb098`. The score is white-relative Stockfish centipawns. The result byte is 1/2. Training uses `sigmoid(cp / 400)`, which is `NSCE_WDL=0`.

The full 416 million positions and the old 320-superbatch schedule are the GTX 1650 path. This machine has no GPU.

## Trainer

Current bullet (rustc 1.99, cloned 18 Oct 2026) builds a mock device unless `--features cuda` or `rocm` is on, and then refuses to step. `train/train_hl_cpu.py` trains the same graph and the same init (FT bias 0.15, hidden stdev divided by 4, hidden bias 0.4) with AdamW (decay 0.01, clip ±1.98). Constant learning rate 0.001, batch 1024, 12 epochs, seed 20261018.

| Epoch | Loss | MAE on a 4096-row training slice (cp) |
| ---: | ---: | ---: |
| 1 | 0.01271 | 122.5 |
| 6 | 0.00568 | 87.1 |
| 12 | 0.00434 | 78.3 |

Quantised export `nets/nsceper1_hl_lichess.bin`, 853 228 bytes, SHA-256 `6b85ecb5a2c2dd4ad6359ec757d32dfbf6d4ad2f8d21de827627ad698b4a9594`.

## Holdout, engine, extras off

2000 positions the bin never saw. The engine loaded the packed net. Two FENs produced no eval line. On the other 1998, white-relative engine cp versus the Stockfish label:

- MAE **157.6 cp**
- sign agreement **75.2%**
- correlation **0.404**

The training-slice MAE above is the same rows the optimiser just saw. The holdout number is the one that counts.

## Games

At 100 ms, 200 games, UHO, seed 20261018, the promoted 768×128 net scored **167-9-24**, **+311.8 ± 62.6** Elo against this net. [Screen](../20261018_hl_lichess_screen/report.md).
