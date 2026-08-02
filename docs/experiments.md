# Experimental protocol and frozen baseline

## Baseline (canonical)

| Setting | Value |
| --- | --- |
| Binary | `build/nsce` (Release, NSCE 0.8+) |
| UseNNUE | true |
| UsePolicy | false |
| UseSearchController | false |
| Threads | 1 |
| Hash | 16 |
| Time control | `movetime=100` (ablations) / `tc=10+0.1` (ladder when cutechess available) |

Apply via UCI before every match:

```
setoption name Hash value 16
setoption name Threads value 1
setoption name UseNNUE value true
setoption name UsePolicy value false
setoption name UseSearchController value false
```

Config files: [tools/configs/baseline.uci](../tools/configs/baseline.uci).

## Weekly KPIs

Record under `experiments/YYYYMMDD/report.md`:

- ΔElo (or score) on current ladder rung
- nodes/move
- time overrun rate (must be 0)
- Elo/nodo proxy
- timeouts / illegal moves (must be 0)

## Ablation matrix

Run:

```bash
python3 tools/ablation_match.py --matrix --outdir experiments/$(date +%Y%m%d)
```

Matches:

1. baseline vs HCE (`UseNNUE=false`)
2. baseline vs Policy on
3. baseline vs Controller on
4. baseline vs Policy+Controller

All four comparisons are pre-registered and always run. The matrix is exploratory:
promote a candidate only after a separate confirmation SPRT on fresh games.

## Elo ladder

```bash
python3 tools/elo_ladder.py --outdir experiments/$(date +%Y%m%d)
```

Peldaños: depth-ladder self-play → weak NSCE → Stockfish limitado (si `stockfish` en PATH).

## Stockfish (local)

Binary under `third_party/stockfish/` (gitignored). Ensure:

```bash
export PATH="$HOME/.local/bin:$PATH"   # symlink created on install
# or: export STOCKFISH=/path/to/stockfish
```

Verify: `stockfish <<< $'uci\nquit' | head -3`

## Reproducibility contract

Every runner uses a deterministic `--seed` and color-reversed opening pairs. Therefore
`--games` and `--max-games` must be positive even numbers. Each output directory includes
`manifest.json` with:

- Git commit and dirty state
- SHA-256 of engine, configs, openings and CMake cache
- CPU, OS, compiler and Python versions
- Full command line, seed, time control and adjudication parameters

Do not compare reports if engine/config/opening hashes differ unexpectedly. Do not compare
results produced from a dirty tree unless the exact binary hash is retained.

## Adjudication

The old post-game depth-3 adjudication was biased because one of the compared engines acted
as referee. It has been removed. The internal runner now:

- uses checkmate/stalemate/draw from the game state;
- adjudicates evaluation only after both engines, alternating by ply, sustain the same
  `±800 cp` sign for 6 plies after ply 20;
- declares max-ply positions draws;
- aborts on `bestmove 0000` in an ongoing position instead of silently scoring it.

For publishable matches, prefer `cutechess-cli` with a separately pinned adjudication policy.

## Candidate promotion gates

1. `ctest` including sanitizers and perft must pass.
2. Fixed-depth benchmark must not regress materially unless an Elo gain justifies it.
3. Run the four-way matrix on paired openings; treat it as exploratory.
4. Select exactly one candidate and run a fresh SPRT, normally:

```bash
python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/candidate.uci \
  --elo0 -5 --elo1 5 \
  --max-games 400 --movetime 100 --seed 20260802 \
  --outdir experiments/$(date +%Y%m%d)-candidate
```

5. Accept/reject only at opening-pair boundaries. Never stop because a point estimate looks
   favorable.
6. Re-run accepted candidates against a stronger Stockfish rung with fresh openings.

When thread counts differ, wall time is not equal compute. Official comparisons use equal
threads, hash, affinity and wall time; additionally report CPU-seconds where available.
`Elo/nodo` is diagnostic only because pruning changes the meaning and cost of a node.
