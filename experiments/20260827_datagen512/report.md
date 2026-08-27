# Datagen increment — 256 → 512 self-play games

Date: 2026-08-27. Driver: `train/run_datagen.sh` (`TARGET_GAMES=512`, 100 ms,
`--both-colors`, `collect_leaves --append`).

Self-play resume from 256 games in `train/data/selfplay_colors.jsonl`. Unfinished
`max_plies` stay unlabeled.

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After increment | 512 | 170 | 129 | 63 | 150 |

Finished games 362. `collect_leaves` planned 1086 path-root searches, skipped 672
already in `leaves_with_results.seen.sqlite`, ran **414**. Appended **3 103 231**
new unique `search_leaf` / path FENs (game WDL only on path roots). Dump is
gitignored under `train/data/`.
