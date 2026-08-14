# Experimental protocol and frozen baseline

Compiled claims, rejections, and ladder state: [docs/knowledge.md](knowledge.md).
Update that file after every SPRT, ladder, or diagnostic — do not only write `experiments/*/report.md`.

## Baseline (canonical)

| Setting | Value |
| --- | --- |
| Binary | `build/nsce` (Release, NSCE 0.8+) |
| UseNNUE | true |
| EvalFile | internal (frozen HCE-distilled network) |
| UsePolicy | false |
| UseSearchController | false |
| Threads | 1 |
| Hash | 16 |
| Time control | `movetime=100` (ablations) / `tc=10+0.1` (ladder when cutechess available) |
| Openings | Prefer `tools/openings_balanced.epd` for exploratory lab; regenerate with `tools/generate_openings.py` |

Apply via UCI before every match:

```
setoption name Hash value 16
setoption name Threads value 1
setoption name UseNNUE value true
setoption name EvalFile value internal
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
python3 tools/ablation_match.py --matrix --openings tools/openings_balanced.epd \
  --outdir experiments/$(date +%Y%m%d)
python3 tools/ablation_match.py --search-matrix --openings tools/openings_balanced.epd \
  --outdir experiments/$(date +%Y%m%d)_search
```

Matches:

1. baseline vs HCE (`UseNNUE=false`)
2. baseline vs Policy on
3. baseline vs Controller on
4. baseline vs Policy+Controller
5. search-matrix: baseline vs one-feature-off for TT/SEE/LMR/null/futility/LMP/razor/RFP

The trained NNUE is a separate candidate, `tools/configs/trained_nnue.uci`; do not
silently replace the frozen baseline when measuring it.

All comparisons are pre-registered and always run. The matrix is exploratory:
promote a candidate only after a separate confirmation SPRT on fresh games.
See also [docs/measurement.md](measurement.md).

## Elo ladder

```bash
python3 tools/elo_ladder.py --outdir experiments/$(date +%Y%m%d)
```

Peldaños: depth-ladder self-play → weak NSCE → Stockfish limitado (si `stockfish` en PATH).

## Stockfish (local)

Binaries under `third_party/stockfish/` (gitignored). **Do not use PATH.** Pin
official Stockfish 18 and the current development snapshot with
`tools/freeze_targets.py`; `elo_ladder.py --stockfish` defaults to
`third_party/stockfish/stockfish-18`.

Historical ladder reports labeled "SF18" used PATH `stockfish`, which is
**Stockfish 17**. Keep that binary as `stockfish-17` for provenance; new rungs
use the frozen SF18 hash.

Verify:

```bash
printf 'uci\nquit\n' | third_party/stockfish/stockfish-18 | head -3
```

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
Treat `movetime < 50 ms` as timer/scheduler testing only: `sprt.py` rejects it unless
`--allow-short-tc` is explicitly supplied, and every manifest records
`exploratory_short_tc`. At short controls, OS jitter and adjudication account for too much
of the result variance.

Report opening pairs, not just games, as the effective independent sample count. Before
promotion, repeat the result at a longer control and run an adjudication sensitivity check
(higher threshold or no evaluation adjudication). A short-control `inconclusive` result is
evidence of insufficient information, not evidence that the engines are equal.

## Candidate promotion gates

1. `ctest` including sanitizers and perft must pass.
2. Fixed-depth benchmark must not regress materially unless an Elo gain justifies it.
3. Run the four-way matrix on paired openings; treat it as exploratory.
4. Select exactly one candidate and run a fresh SPRT, normally:

```bash
python3 tools/sprt.py \
  --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/candidate.uci \
  --openings tools/openings_balanced.epd \
  --elo0 -5 --elo1 5 \
  --max-games 400 --movetime 100 --seed 20260802 \
  --outdir experiments/$(date +%Y%m%d)-candidate
```

5. Accept/reject only at opening-pair boundaries using the pair-level pentanomial LLR.
   Never stop because a point estimate looks favorable. Older trinomial SPRT JSON files are
   incompatible with `--resume`.
6. Re-run accepted candidates against a stronger Stockfish rung with fresh openings.

When thread counts differ, wall time is not equal compute. Official comparisons use equal
threads, hash, affinity and wall time; additionally report CPU-seconds where available.
`Elo/nodo` is diagnostic only because pruning changes the meaning and cost of a node.
