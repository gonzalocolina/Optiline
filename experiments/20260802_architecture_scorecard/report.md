# Architecture scorecard — 2026-08-02

Implementation of the measurement + improvement plan: telemetry, ablation flags,
persistent SMP pool, multi-FEN bench/profiling, HalfKP runtime path, lab upgrades.

## Verification

| Gate | Result |
| --- | --- |
| `ctest` Release (`build`) | 33/33 pass |
| `ctest` stats (`build-stats`, `NSCE_STATS=ON`) | 33/33 pass |
| `ctest` ASan (`build-asan`) | 33/33 pass |
| Python experiment unit tests | pass (incl. pentanomial SPRR) |
| Openings book | `tools/openings_balanced.epd` — 128 FENs |

## Fixed-work benchmarks

Suite: 6 positions, depth 9, Release+stats.

| Threads | Nodes | Wall ms | NPS | Score | Best |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 455863 | 238 | 1.92M | 377 | 95701 |
| 4 | 1014647 | 254 | 3.99M | 377 | 95701 |

Notes:

- Persistent helper pool no longer spawns/joins threads per iterative deepening step.
- At depth 9 the wall-time speedup is modest; node inflation remains (shared TT / root race).
- Root LMR was tried and **reverted**: it reduced nodes but hurt parallel NPS and score consistency.

Perft(6) after magic/PEXT slider tables: **119060324 in 1657 ms** (was ~2143 ms before tables).

## Telemetry snapshot (depth 9, 1 thread)

- qnodes ≈ 65% of nodes
- first-move cutoff ≈ 91%
- LMR researches / attempts ≈ 1.7%
- SEE order calls still dominate capture handling; quiescence reuses ordered SEE instead of recomputing

## Profiling

`perf` is blocked on this host (`kernel.perf_event_paranoid=4`). Fallback Callgrind:

- Artifact: `experiments/profiles/search.callgrind`
- Inclusive hot path: `Search::quiescence` / `Search::search`
- Pre-magic exclusive hotspot: `rook_attacks_bb` ≈ 15% Ir

Helper: `bash tools/profile_engine.sh`

## Architecture deliverables

1. **`NSCE_STATS`** — worker-local counters, aggregated into `Search::last_stats()`, printed as `info string stats…`.
2. **Ablation UCI flags** — `UseTT`, `UseSEE`, `UseLMR`, `UseNullMove`, `UseFutility`, `UseLMP`, `UseRazoring`, `UseRFP` frozen in `tools/configs/baseline.uci`.
3. **`--search-matrix`** in `tools/ablation_match.py`.
4. **Persistent SMP pool** + stop/join in destructor.
5. **HalfKP runtime** (`NSCEHFKP`) + `train/train_halfkp.py` (requires ≥50k samples by default).
6. **Lab** — `tools/generate_openings.py`, balanced EPD, pair-level pentanomial SPRT.
7. **Docs** — `docs/measurement.md`, README / experiments / train updates.

## Search-matrix smoke (n=8 games / feature, 80 ms)

Tooling validation only — CIs are huge (±73…131 Elo). Directional sketch:

| Feature disabled | Elo A−B (baseline − challenger) |
| --- | ---: |
| TT | +89 ± 131 |
| SEE | +44 ± 106 |
| LMR | +89 ± 131 |
| Null move | +89 ± 131 |
| Futility | −44 ± 106 |
| LMP | −44 ± 106 |
| Razoring | +44 ± 106 |
| RFP | +0 ± 73 |

Do **not** promote or remove features from this smoke. Re-run with ≥40 games and
`movetime ≥ 100` on `tools/openings_balanced.epd` before interpreting.

## Remaining limits (not claimed solved)

- HalfKP is runtime-ready, not strength-promoted; corpus is still the 2k bootstrap.
- Multi-thread wall-time scaling is incomplete; equal-score at depth 9 is encouraging but not a strength claim.
- `perf` needs a lower `perf_event_paranoid` or root/CAP_PERFMON.
- TSan binary builds but this kernel rejects its memory mapping at runtime.
- Promotion still needs a fresh non-short-TC SPRT on `tools/openings_balanced.epd`.

## Next recommended experiments

```bash
python3 tools/ablation_match.py --search-matrix \
  --openings tools/openings_balanced.epd \
  --games 40 --movetime 100 --seed 20260802 \
  --outdir experiments/$(date +%Y%m%d)_search_ablation

python3 tools/sprt.py \
  --cfg-b tools/configs/trained_nnue.uci \
  --openings tools/openings_balanced.epd \
  --max-games 400 --movetime 100 --seed 20260803
```
