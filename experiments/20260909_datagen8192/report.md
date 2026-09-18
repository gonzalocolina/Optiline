# Datagen 8192 — self-play and leaf append done

Date: 2026-09-09. Resume from the 2026-08-29 pause at 6002.
Self-play: `WORKERS=13` `TARGET_GAMES=8192` `MOVETIME=100`, current promoted
`baseline.uci` (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`). Leaf append:
4 niced spawn workers (not Lazy SMP) so `./tools/play.sh` stayed usable.
`collect_leaves` workers now **spawn** instead of fork, so they do not inherit
the parent's sqlite handle.

Self-play finished in 41m52s. Leaf append finished in 16m08s after earlier
agent-tied runs were SIGTERM'd (sqlite skip-list kept the partial roots).

| | Games | 1-0 | 0-1 | draw | unfinished |
| --- | ---: | ---: | ---: | ---: | ---: |
| After 4096 | 4096 | 1299 | 1119 | 527 | 1151 |
| Pause | 6002 | 1891 | 1653 | 792 | 1666 |
| **Done** | **8192** | **2480** | **2184** | **1099** | **2429** |

Increment 6002→8192: **589-531-307** + 763 unfinished. Finished games **5763**.
JSONL: `train/data/selfplay_colors.jsonl`.

`collect_leaves --append` (`go nodes 25000`, 3 path roots per finished game):
17289 planned searches, skip **11809** already in sqlite, **5480** new roots.
This run wrote **36 817 302** unique leaves. Dump is 24G jsonl + 8.8G sqlite.
Path FENs from 8192 games: **648 979** (`train/data/selfplay_path.jsonl`).

Do not promote `EvalFile`. Do not stamp WDL onto hypothetical leaves.
Next: disjoint 40k@8000 result-weight 0 mix vs the promoted 768
([search 40k 8192](../20260909_search_leaves40k_8192/)).
