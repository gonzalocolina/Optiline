# NSCE 25k-node self-distill: 768 MAE fail, KAT MAE win, equal-node loss

Date: 2026-08-14. Teacher: frozen v0.10 (`EvalFile=internal`, extras on, Hash 16)
`go nodes 25000` on the first 200k FENs of `train/data/lichess_evals_1m.jsonl`.
Labels: `train/data/nsce_nodes25k.jsonl` (200000 rows, 0 null `score_cp`,
sha256 `13753581379e…`). Do not compare these MAE numbers to the 114 cp Lichess
holdout.

Holdout for engine MAE: `sha256(fen) % 10 == 0` (N=20039), same split as the
trainers. Baseline column is always internal + extras.

## 768×128 from scratch (`nets/nnue_nsce25k.bin`, extras on)

16 epochs, batch 256, seed 20260814. Trainer float val MAE 95.4 → 80.9 cp.

Engine eval vs NSCE 25k-node labels:

| Net | MAE cp | RMSE cp |
| --- | ---: | ---: |
| internal + extras | 65.1 | 123.9 |
| `nnue_nsce25k.bin` + extras | 84.8 | 133.3 |

**−19.8 cp (−30%)**. MAE did not improve, so 500k labeling and equal-node for
this 768 were skipped. From-scratch 768 on 200k search scores is worse than the
frozen HCE-distilled net.

## KAT (`nets/kat_nsce25k.bin`, extras off)

16 epochs, batch 256, seed 20260814, `--minimum-samples 50000`. Best float val
MAE 58.2 cp (epoch 15).

Engine eval vs the same labels:

| Net | MAE cp | RMSE cp |
| --- | ---: | ---: |
| internal + extras | 65.1 | 123.9 |
| `kat_nsce25k.bin`, extras off | 58.1 | 94.8 |

**+6.9 cp (+10.7%)**. MAE gate passed. Equal-node next, not SPRT.

## Equal node (`go nodes 25000`, N=40)

- A: `tools/configs/baseline.uci` (internal + extras)
- B: `tools/configs/kat_nsce25k.uci` (KAT, extras off)
- Openings: `openings_balanced.epd`, seed 20260814, max plies 60
- W-D-L from baseline: **17-22-1** (score **0.700**, **+147 ± 71**)
- KAT score **0.300** (one win)
- Nodes/game: baseline 379k, KAT 372k
- Time/game: baseline 622 ms, KAT 590 ms

Need challenger score clearly > 0.5. Fail. **No 100 ms SPRT. `baseline.uci`
unchanged.**

Better leaf MAE on the teacher's search scores did not make a stronger search
companion. Same qualitative failure as the Lichess KAT (MAE/equal-node can
diverge from equal-time, and here even equal-node lost). Do not label 500k for
this KAT expecting the match to flip.
