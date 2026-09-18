# Datagen increment — 512 → 1024 self-play games

Date: 2026-08-27. Driver: `train/run_datagen.sh` (`TARGET_GAMES=1024`, 100 ms,
`--both-colors`, `collect_leaves --append`). Seed is not used; openings are
`tools/openings_balanced.epd` in schedule order. Did not re-collect the old
4.6M dump.

Self-play `--resume` from 512 games in `train/data/selfplay_colors.jsonl`.
Unfinished `max_plies` stay unlabeled (`result` absent).

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After 512 | 512 | 170 | 129 | 63 | 150 |
| After increment | 1024 | 323 | 275 | 120 | 306 |

Finished games 718. Self-play wall 2h01m. `collect_leaves` planned 2154
path-root searches, skipped 1413 already in `leaves_with_results.seen.sqlite`,
ran **741**. Appended **4 886 429** new unique `search_leaf` / path FENs (game
WDL only on path roots). Dump is gitignored under `train/data/`.

Log: `experiments/20260827_datagen1024/datagen.log`.
