# NSCE-KAT first corpus (≥50k)

Date: 2026-08-13. Architecture `NSCEKAT1`: 32 horizontally-mirrored king
buckets × 768 + train-time PS factorization (folded at export) + 12-dim
threat residual. MIT-clean; labels only, no Stockfish net files.

## Data

- Source: `https://database.lichess.org/lichess_db_eval.jsonl.zst` streamed
  through `train/import_lichess_evals.py --limit 120000`
- Unique FENs: 120000. White-POV `cp` from the deepest non-mate PV.
- Split: 108015 train / 11985 holdout (FEN hash % 10 == 0)

## Train

```
.venv/bin/python train/train_kat.py \
  --data train/data/lichess_evals_120k.jsonl \
  --epochs 12 --batch-size 256 --learning-rate 0.0004 \
  --minimum-samples 50000 --seed 20260813
```

Holdout MAE 102.2 cp, RMSE 198.0 cp (toy 768×128 on 2k labels: ~325 cp MAE).
Quantized `nets/kat_candidate.bin` is 6.1 MB (`NSCEKAT1`).

## Runtime smoke

- 44/44 unit tests, including KAT load / mirror refresh / threat counts
- Startpos `eval`: internal 42 cp, KAT 40 cp
- UCI `bench 8`: internal 17412 nodes / ~3.5M nps; KAT 43148 nodes / ~2.3M nps
  (threat maps + larger sparse table)

## Not done

No SPRT vs `tools/configs/baseline.uci`. Do not replace `EvalFile=internal`
until that gate. Next scale: keep streaming the same dump toward millions.
