# Datagen increment — 2048 → 4096 self-play games

Date: 2026-08-29. Driver: `train/run_datagen.sh` (`TARGET_GAMES=4096`, 100 ms,
`--both-colors`, `collect_leaves --append`, 15×1-thread workers, not Lazy SMP).
`baseline.uci` unchanged.

Self-play `--resume` from 2048 games in `train/data/selfplay_colors.jsonl`.
Unfinished `max_plies` stay unlabeled.

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After 2048 | 2048 | 655 | 572 | 248 | 573 |
| After increment | 4096 | 1299 | 1119 | 527 | 1151 |

Finished games 2945. Self-play wall **31m37s**. `collect_leaves` planned 8835
path-root searches, skipped 5895 already in `leaves_with_results.seen.sqlite`,
ran **2940**. First pass crashed at **2897/2940** (`database or disk is full`
from an unbounded `leaves_with_results.raw.jsonl`). After deleting that 3.6G
working file and rewinding telemetry each search, `--append` skipped 8791 and
finished the remaining **44** in 13s (**+268 762** unique). Increment total
**+19 471 553** unique `search_leaf` / path FENs (game WDL only on path roots).

Dump is gitignored under `train/data/`. `/` still ~98% full (13G jsonl + 4.7G
sqlite). Do not raise `TARGET_GAMES` until there is several GB free.

Log: `experiments/20260829_datagen4096/datagen.log`.
