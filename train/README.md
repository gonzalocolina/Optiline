# Training pipeline (Phases 4–7 + lab)

## Self-play with real outcomes

```bash
python3 train/selfplay.py --games 8 --movetime 80 --config tools/configs/baseline.uci
```

Uses UCI `status` (`checkmate` / `stalemate` / `draw` / `ongoing`).

## Distillation labels

```bash
python3 train/distill.py --depth 10 --positions 64 -o train/data/distill.jsonl
# uses Stockfish if on PATH, else NSCE
```

## Fit policy / controller binaries

```bash
bash train/run_train_loop.sh
```

## SPRT candidate vs baseline

```bash
python3 tools/sprt.py --cfg-a tools/configs/baseline.uci --cfg-b tools/configs/controller.uci --max-games 100
```
