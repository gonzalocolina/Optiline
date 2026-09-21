# Local Stockfish binaries (not committed)

Do not copy Stockfish source or `.nnue` weights into this tree. Binaries are
gitignored; pin them with `tools/freeze_targets.py` and record hashes in
`experiments/frozen-targets/manifest.json`.

| File | Identity | Role |
| --- | --- | --- |
| `stockfish` / `stockfish-17` | Stockfish 17 (2024-09-06) | Historical PATH/ladder binary. Pre-2026-08-14 reports labeled this "SF18". |
| `stockfish-18` | Official [Stockfish 18](https://github.com/official-stockfish/Stockfish/releases/tag/sf_18) ubuntu-x86-64-avx2 | Historical stable pin (north star until 2026-09-21) |
| `stockfish-19` | Official [Stockfish 19](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19) linux-x86-64-universal | Frozen stable reference (north star) |
| `stockfish-dev` | [dev-20260825-2edd935b](https://github.com/official-stockfish/Stockfish/releases/tag/stockfish-dev-20260825-2edd935b) linux-x86-64-universal | Stale vs SF19; refresh only with a snapshot newer than `sf_19` |

```bash
python3 tools/freeze_targets.py \
  --engine build/nsce \
  --stockfish19 third_party/stockfish/stockfish-19 \
  --stockfish18 third_party/stockfish/stockfish-18 \
  --stockfish-dev third_party/stockfish/stockfish-dev \
  --stockfish-historical third_party/stockfish/stockfish-17 \
  --out experiments/frozen-targets/manifest.json
```
