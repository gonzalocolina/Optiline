# Datagen increment — 1024 → 2048 self-play games

Date: 2026-08-29. Driver: `train/run_datagen.sh` (`TARGET_GAMES=2048`, 100 ms,
`--both-colors`, `collect_leaves --append`). Remainder after a serial interrupt
at 1833 games ran with **15 workers** (`nproc-1`): independent 1-thread engines,
not Lazy SMP. `baseline.uci` unchanged.

Self-play `--resume` from 1024 games in `train/data/selfplay_colors.jsonl`.
Unfinished `max_plies` stay unlabeled.

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After 1024 | 1024 | 323 | 275 | 120 | 306 |
| After increment | 2048 | 655 | 572 | 248 | 573 |

Finished games 1475. Parallel remainder (215 games) wall **3m19s**.
`collect_leaves` planned 4425 path-root searches, skipped 2902 already in
`leaves_with_results.seen.sqlite`, ran **1523**. Appended **10 129 214** new
unique `search_leaf` / path FENs (game WDL only on path roots). Dump is
gitignored under `train/data/`.

Log: `experiments/20260827_datagen2048/datagen.log`.
