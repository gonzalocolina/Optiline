# KAT 1M × 16 epochs vs frozen baseline (SPRT)

Date: 2026-08-13. Same 1M Lichess corpus and hidden 128 as the 8-epoch net
that already lost H0. This run only adds epochs.

## Train

- 16 epochs, batch 512, lr 4e-4, seed 20260813
- Holdout MAE **114.1 cp**, RMSE 208.6 cp (epoch 8 was 117.0 / 217.5)
- MAE flattened after epoch 11. Target ~70 cp was not reached; do not raise hidden size.
- Checkpoint: `train/checkpoints/kat_1m.npz` (gitignored)

## Diagnostic (8-epoch net, same architecture)

- Equal-node 25k, 20 games: 4-12-4 vs internal (score 0.500). See
  `experiments/20260813_kat_equal_nodes/report.md`.
- Startpos depth 10: KAT searches ~3× more nodes at similar nps.

## SPRT

- `kat.uci` vs `baseline.uci`, 100 ms, min 40 / max 200, seed 20260814

| Decision | W-D-L (KAT) | Games | LLR |
| --- | ---: | ---: | ---: |
| inconclusive | 36-86-78 | 200 | −2.11 |

Point estimate still negative. Do **not** replace `EvalFile=internal`.

## Next

More epochs on 1M will not get MAE to 70. Stream ~5M labels (or better teacher
cp) before another SPRT. Keep extras() off for king-bucket nets.
