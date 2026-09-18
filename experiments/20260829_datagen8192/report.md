# Datagen — paused at 6002 / 8192 (self-play only)

Date: 2026-08-29. Driver was `TARGET_GAMES=8192` `WORKERS=13` `MOVETIME=100`.
Stopped on request once `selfplay_colors.jsonl` reached **6002** games
(SIGTERM of the datagen process group). **`collect_leaves` did not run.**
Leaf dump is still the 4096-game corpus. `baseline.uci` unchanged.

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After 4096 | 4096 | 1299 | 1119 | 527 | 1151 |
| Stopped | **6002** | **1891** | **1653** | **792** | **1666** |

Finished 4336 (3544 mates, 788 draws, 4 stalemates). JSONL has 0 truncated lines.

Resume later (self-play remainder, then append leaves):

```bash
WORKERS=13 TARGET_GAMES=8192 MOVETIME=100 bash train/run_datagen.sh
```

`--resume` skips the 6002 games already on disk. Or collect only the new finished
roots against the current 4096 sqlite index with `collect_leaves --append`.
