# Training pipeline (Phases 4–7)

## Export default NNUE

```bash
python3 train/export_nnue.py -o nets/nnue_default.bin
```

## Self-play under time budget + fit policy/controller

```bash
bash train/run_train_loop.sh
# or:
python3 train/selfplay.py --games 8 --movetime 50
python3 train/train_from_selfplay.py --telemetry /tmp/nsce_telem_train.csv
```

Load into the engine:

```
setoption name PolicyFile value nets/policy.bin
setoption name ControllerFile value nets/controller.bin
setoption name EvalFile value nets/nnue_default.bin
```

Reward used in self-play JSONL: `result - λ * mean_nodes` (scaffold for Phase 7 RL). Replace labeling with real game outcomes / SPRT data for serious experiments.
