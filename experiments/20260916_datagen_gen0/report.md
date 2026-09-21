# nsce_datagen gen0 — started 2026-09-16

```text
./build/nsce_datagen --out train/data/gen0.bin --games 1200000 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1
```

- Started after P0.3 weekly KPI finished (no timed match on `build/nsce`).
- `train/data/nsce_search_mix_40k.jsonl` kept. `df -h .` showed 44 G free.
- Early rate ~2430 pos/s on 14 threads (~12–14 h to ~100–120 M positions). ~6.0 M positions at ~41 min (PID 47407).
- Overlapped 12-thread + 14-thread writers were killed; this run is a single 14-thread process on a fresh `gen0.bin`.
- Do not train until this file is complete and shuffled with bullet-utils. Do not fake a net.
- Watcher: `bash tools/watch_datagen_then_train.sh` (starts shuffle+bullet only after `datagen done` and ≥100 M positions). After a reboot: `bash tools/resume_gen0.sh`.

Stdout: `experiments/20260916_datagen_gen0/stdout.log`

**Reboot 2026-09-16 ~17:38.** PID 47407 died at ~7.95 M records (243 M, 32-aligned, `bullet-utils validate` clean). No `datagen done`. Resumed **append** with `--seed 2 --games 1120000` (do not replay seed 1). Watcher restarted; trains only after a new `datagen done` and **file** ≥100 M positions. 2026-09-16 20:24: file **31.7 M** records, this run ~23.7 M at ~2480 pos/s.

**2026-09-16 20:50 faster writer.** SIGTERM PID 6086 (`build/nsce_datagen` 12:43, ~2493 pos/s) at **35 743 192** aligned records. Resume seed 3, 689 341 games, `build-per1/nsce_datagen` PID 26176, 14 threads, ~3480 pos/s.

**Paused 2026-09-16 21:57 (user).** SIGTERM writer then watcher. File **49 668 542** records (1 589 393 344 bytes, 32-aligned). No `datagen done`. Do not train.

**Resumed 2026-09-18 10:22.** `bash tools/resume_gen0.sh` append seed 4, 544 286 games, `build-per1/nsce_datagen` PID 90052, 14 threads, ~3410 pos/s. Watcher PID 90055. ~4.1 h to 100 M.
- **Paused 2026-09-18 11:47 (user).** SIGTERM watcher 90055 then writer 90052. File **67 076 005** records (2 146 432 160 bytes, 32-aligned). No `datagen done`.
- **Resumed 2026-09-18 13:48.** `bash tools/resume_gen0.sh` append seed 5, 362 958 games, `build-per1/nsce_datagen` PID 7032, 14 threads. Watcher restarted 14:08 as PID **12125**. From **67 076 005**. Warmed to ~3260 pos/s.
- **Done 2026-09-18 18:01.** `datagen done:` 359 836 games this seed (W 115 502 D 60 394 L 183 940, discarded 3122), 34 565 728 positions, 3261 pos/s, 10598 s. File **101 641 733** records (3 252 535 456 bytes, 32-aligned). Watcher 12125 exec'd `train/run_bullet.sh`. Shuffle validated. CUDA train ~3.3 M pos/s, 320 superbatches, checkpoints every 10.
- **Train paused 2026-09-18 20:16 (user).** SIGTERM `run_bullet.sh` 12125 then CUDA `examples/nsce` 28654. Checkpoint **`train/bullet_checkpoints/nsce-250`** has optimiser_state.
- **Train resumed 2026-09-18 21:04.** `bash train/run_bullet.sh` PID 5449, CUDA 5476. Shuffle re-validated (101 641 733, no invalid). Resume checkpoint 250, start superbatch 251/320.
