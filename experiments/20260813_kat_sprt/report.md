# KAT 1M vs frozen baseline (SPRT)

Date: 2026-08-13. Candidate: `NSCEKAT1` trained on 1M unique Lichess evals.
HCE `extras()` stay off for king-bucket nets. Baseline: `EvalFile=internal`.

## Data / train

- Stream: `lichess_db_eval.jsonl.zst` → `train/import_lichess_evals.py --limit 1000000`
- Unique FENs: 1,000,000. SHA-256 `78750d1e9e4b…`
- Split: 899780 train / 100220 holdout
- 8 epochs, batch 512, lr 4e-4, seed 20260813
- Holdout MAE **117.0 cp**, RMSE 217.5 cp (still falling at epoch 8; target ~70 cp not reached)
- Hidden size kept at 128. Quantized `nets/kat_candidate.bin` 6.1 MB (`NSCEKAT1`)

120k-corpus MAE was 102 cp on a smaller holdout; the 1M holdout is a harder, more
diverse slice. MAE did not plateau, so hidden size was not raised.

## SPRT

- `tools/configs/kat.uci` vs `tools/configs/baseline.uci`
- `openings_balanced.epd`, seed 20260813, 100 ms, max plies 80
- `--elo0 -5 --elo1 5`, min 40 / max 400 games

| Decision | W-D-L (KAT) | Games | LLR |
| --- | ---: | ---: | ---: |
| **accept_H0_baseline_not_worse** | 39-112-85 | 236 | −3.00 |

Do **not** replace `EvalFile=internal` in `tools/configs/baseline.uci`. KAT is
slower (~threat maps + larger table) and not yet stronger at equal time.

## Next

More epochs and/or 5M labels before another SPRT. Keep extras() gated off.
