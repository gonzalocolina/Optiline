# Lab knowledge

Compiled findings from NSCE experiments. Raw match logs stay under
`experiments/YYYYMMDD_*/`. This file is the **working model**: what is frozen,
what has been measured, what failed, and what to try next.

| Field | Value |
| --- | --- |
| Last updated | 2026-08-13 |
| Engine | NSCE 0.10 |
| Frozen baseline | `tools/configs/baseline.uci` — `EvalFile=internal`, `UseSearchController=false`, `UsePolicy=false` |
| Protocol | [hypothesis.md](hypothesis.md), [experiments.md](experiments.md), [measurement.md](measurement.md) |

## How to add knowledge

After every experiment (SPRT, ladder, bench, ablation):

1. Keep the raw report in `experiments/YYYYMMDD_name/`.
2. Append a dated bullet under [Findings log](#findings-log). Do not edit or delete older log entries.
3. If the result **changes a claim**, update [Current beliefs](#current-beliefs), [Rejected](#rejected--do-not-repeat), [Ladder](#ladder-position), or [Next levers](#next-levers), and set **Last updated**.
4. Quote W/D/L, N, TC, seed, and the experiment path. Point estimates without N or a CI are not knowledge.
5. One candidate per SPRT. Never promote `EvalFile` / `UseSearchController` / `UsePolicy` in `baseline.uci` without pentanomial H1.

Suggested log line:

```text
- YYYY-MM-DD — [claim]. Evidence: W-D-L, N=…, TC=…, seed=… (`experiments/…`). Decision: H0 / H1 / inconclusive / diagnostic.
```

---

## Current beliefs

These are the claims we act on until a later log entry supersedes them.

### Science

- The north star is **equal-compute Stockfish latest** (same threads, TC, hash). Limited `UCI_Elo` is a weekly KPI, not that target. ([hypothesis.md](hypothesis.md))
- Compete on **Elo/time** and **Elo/node**, not by cloning SFNNv13 or copying GPL search. Labels (cp / WDL) are allowed; Stockfish `.nnue` weights are not.
- A feature that wins **fixed nodes** and loses **fixed time** is too expensive, not “almost good.” Interpret the two matches separately. ([measurement.md](measurement.md))
- `Elo/nodo` is diagnostic only: pruning changes what a node means.

### Frozen baseline (v0.10)

- Eval: HCE-distilled `768×128×1` (`EvalFile=internal`) **plus** classical `extras()` (mobility, files, outposts, hanging, king).
- King-bucket nets (KAT / HalfKP): **`extras()` off**. The residual fights the net and biases learning.
- Search: PVS, TT, LMR, NMP with verify, RFP, razoring, futility, LMP, ProbCut, IIR, singular extensions (double SE on PV only), continuation 1/2/4/6, pick-next, QS fail-soft, quiet SEE, Lazy SMP. Ablation flags freeze each of these in `baseline.uci`.
- Policy and search controller: **off** on the frozen baseline.

### Measurement pitfalls (paid for in lab time)

- **N=20** Elo intervals on the SF ladder are too wide to promote. Use **N≥40** (paired colors).
- Stockfish has no `status`. The oracle must always be **NSCE**. Otherwise `bestmove 0000` after mate aborts the match ([20260813_sf18_1600](../experiments/20260813_sf18_1600/report.md)).
- Pair-level pentanomial LLR with near-zero empirical variance explodes after one opening pair. Floor per-pair variance at **0.04** and do not accept H0/H1 before **`--min-games 40`**. A 2-game H1 is invalid ([20260813_controller_fitted](../experiments/20260813_controller_fitted/report.md)).
- Do not compare holdout MAE across different corpora (120k vs 1M). The 1M holdout is harder.
- `movetime < 50 ms` is exploratory; `sprt.py` refuses it unless `--allow-short-tc`.
- Do not compare reports unless engine / config / opening hashes match (`manifest.json`).

### Eval (KAT)

- `NSCEKAT1`: 32 horizontally-mirrored king buckets × 768, PS factorization folded at export, 12-dim dense threat residual. MIT-clean.
- Holdout MAE on 1M Lichess evals plateaus around **114 cp** at 16 epochs (hidden 128, batch 512, lr 4e-4). Target ~70 cp was not reached. **Do not raise `kHidden` until MAE stops falling with more data.**
- At **equal nodes** (25k/move, N=20) 8-epoch KAT vs internal is a coin flip (4-12-4). At **equal time** (100 ms) it loses SPRT. The failure mode is a **bushier tree / less effective depth**, not a 2× nps collapse. Startpos depth 10: similar nps, ~3× more nodes for KAT.
- 120k-corpus MAE 102 cp is not comparable to the 1M holdout.

### Search controller

- Default prior (`NSCECTRL`, `bias=-120`) and fitted `NSCECTL2` (hist, improving, cut_node, SEE) are both **unpromoted**. Clamp stays **[-1, +2]**.
- Fitted weights from 246k self-search LMR events: `w_cut=-11` dominates; `w_see=0`. Ridge MAE 14.4 on the residual. Equal-time SPRT slightly negative / inconclusive.
- Without research/cutoff labels there is nothing useful to learn. Log LMR with `TelemetryFile` while the controller is **off**.
- Re-fit only on the **winning** eval baseline, never mix KAT + controller in one SPRT.

### Policy

- Piece→to + from→to is too weak to beat history. Conditioning a destination head on the KAT accumulator is postponed until KAT wins a SPRT; otherwise it relearns a PST.

---

## Rejected / do-not-repeat

| Idea | Why it is closed | Evidence |
| --- | --- | --- |
| Promote KAT 1M×8 | Lost equal-time SPRT | H0 39-112-85, 236 games, 100 ms ([kat_sprt](../experiments/20260813_kat_sprt/report.md)) |
| Promote KAT 1M×16 | MAE only 117→114; still losing | Inconclusive 36-86-78, LLR −2.11, 200 games ([kat_e16_sprt](../experiments/20260813_kat_e16_sprt/report.md)) |
| More epochs on the same 1M set | MAE flat after epoch 11 | Train history in `nets/kat_candidate.metrics.json` |
| Raise hidden to 256 at 120k–1M | Memorizes; MAE still data-limited | 16-epoch plateau at 114 cp |
| HCE `extras()` on top of KAT/HalfKP | Residual fights the net | Gated in `evaluate()` when `uses_king_buckets()` |
| Promote fitted LMR controller | Slightly negative equal-time | Inconclusive 23-143-34, LLR −0.99 ([controller_sprt](../experiments/20260813_controller_sprt/report.md)) |
| Relax controller clamp before Elo/nodo rises | Current ±1 ply already does not help | Same SPRT |
| Mix extras + KAT + policy + controller in one SPRT | Confounds the gate | Protocol |
| Port more Stockfish search (multi-cut, threat-input sparse nets, SFNNv13) | GPL; keeps us behind Fishtest-tuned constants | License + hypothesis |
| Train from Stockfish `.nnue` files | GPL / not our net | Labels only |
| Treat N=20 SF18 2000 (7-8-5, +35) as a win | Interval ±120; N=40 reversed the sign | [v10](../experiments/20260813_v10/report.md) vs [sf18_2000](../experiments/20260813_sf18_2000/report.md) |
| Use Stockfish as `status` oracle | Aborts on mate (`bestmove 0000`) | [sf18_1600](../experiments/20260813_sf18_1600/report.md) |
| Accept SPRT H1 after one opening pair | Degenerate pentanomial variance | [controller_fitted](../experiments/20260813_controller_fitted/report.md) |

---

## Ladder position

Protocol: 100 ms, 1 thread, Hash 16, `openings_balanced.epd`, NSCE `status` oracle, paired colors.

| Opponent | N | W-D-L (NSCE) | Score | Elo ±95% | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| SF18 Elo 1400 (v0.9) | 20 | 11-6-3 | 0.700 | +147 ± 146 | [sf18_1400](../experiments/20260813_sf18_1400/report.md) |
| SF18 Elo 1400 (v0.10) | 20 | 19-0-1 | 0.950 | +512 ± 1888 | Exploratory N |
| SF18 Elo 1600 (v0.10) | 20 | 15-2-3 | 0.800 | +241 ± 234 | Exploratory N |
| SF18 Elo 1800 (v0.10) | 20 | 8-9-3 | 0.625 | +89 ± 118 | Exploratory N |
| SF18 Elo 2000 (v0.10) | 20 | 7-8-5 | 0.550 | +35 ± 120 | **Superseded** |
| **SF18 Elo 2000 (v0.10)** | **40** | **11-13-16** | **0.438** | **−44 ± 90** | Current rung; CI includes 0 |
| SF18 Elo 2200 (v0.10) | 40 | 10-17-13 | 0.463 | −26 ± 82 | CI includes 0; `UCI_Elo` is not a precise rating |

Stay on **SF18 Elo 2000, N≥40** until a **promoted** eval (or search) wins that rung. Do not treat 2200 as harder than 2000 on a 40-game sample.

**Not played:** unrestricted equal-compute Stockfish 18 (no `UCI_LimitStrength`).

Self-play: NSCE 0.9 vs 0.8 at 100 ms / 60 plies was 2-36-2 (almost all `max_plies` draws) — indecisive.

---

## Next levers

Ordered. Do not skip to a later item to “try something.”

1. **Better eval labels**, same KAT architecture (hidden 128, extras off). Stream ~5M Lichess evals and/or teacher `go nodes` cp. Retrain; SPRT vs frozen internal **only** if holdout MAE moves (goal ~70 cp) or equal-node score is clearly >0.5 at N≥40.
2. **Equal-node vs equal-time** on that new net before promotion. If it wins nodes and loses time, shrink the threat residual / table, do not add search.
3. **Controller re-fit** only after an eval H1. Use research/cutoff telemetry with controller off; keep clamp `[-1, +2]` until Elo/nodo rises at equal time.
4. **Policy on KAT accumulator** only after KAT (or successor) is the frozen eval.
5. **SF18 2000 N≥40** with the new frozen baseline; unrestricted SF only after that rung is clearly won.

Not next: more ProbCut/IIR/SE constants, larger nets at 1M, another 200-game SPRT of the 16-epoch KAT, another N=20 SF ladder.

---

## Findings log

### 2026-08-13

- v0.10 search (ProbCut, NMP verify, double SE on PV, continuation 1/2/4/6, extras on the 768 net) ships. 47/47 tests. Bench ~1.55M nps at depth 10 on startpos.
- vs SF18 limited, N=20, 100 ms: 1400 19-0-1; 1600 15-2-3; 1800 8-9-3; 2000 7-8-5. Exploratory. ([v10](../experiments/20260813_v10/report.md))
- v0.9 vs SF18 1400 N=20: 11-6-3. ([sf18_1400](../experiments/20260813_sf18_1400/report.md))
- v0.9 vs v0.8 self-play 100 ms: 2-36-2. ([search_v09](../experiments/20260813_search_v09/report.md))
- SF18 1600 aborted when Stockfish was the `status` oracle after mate. Re-run with NSCE oracle. ([sf18_1600](../experiments/20260813_sf18_1600/report.md))
- KAT 120k corpus: MAE 102 cp / 12 epochs; no SPRT. ([kat_nnue](../experiments/20260813_kat_nnue/report.md))
- `extras()` disabled for king-bucket nets.
- KAT 1M×8: MAE 117 cp. SPRT vs internal **H0** 39-112-85 (236 games, 100 ms). Not promoted. ([kat_sprt](../experiments/20260813_kat_sprt/report.md))
- Equal-node 25k, N=20: KAT vs internal 4-12-4 (0.500). nps within ~13%; startpos d10 tree ~3×. Failure is tree shape at equal time. ([kat_equal_nodes](../experiments/20260813_kat_equal_nodes/report.md))
- KAT 1M×16: MAE 114 cp, plateau after epoch 11. SPRT **inconclusive** 36-86-78, LLR −2.11, 200 games. Not promoted. ([kat_e16_sprt](../experiments/20260813_kat_e16_sprt/report.md))
- LMR telemetry 246k events → `NSCECTL2`. SPRT vs internal **inconclusive** 23-143-34, LLR −0.99. Not promoted. Clamp stays `[-1, +2]`. ([controller_sprt](../experiments/20260813_controller_sprt/report.md))
- Discarded 2-game controller H1 (LLR ~3500); pentanomial variance floor 0.04 + min 40 games. ([controller_fitted](../experiments/20260813_controller_fitted/report.md))
- SF18 ladder N=40: Elo 2000 **11-13-16** (0.438, −44 ± 90); Elo 2200 **10-17-13** (0.463, −26 ± 82). Current KPI rung is 2000. Unrestricted SF not played. ([sf18_ladder](../experiments/20260813_sf18_ladder/report.md))

### 2026-08-02 (historical; some `experiments/20260802_*` trees may be absent locally)

- Lab protocol: paired openings, pentanomial SPRT, ablation matrix, `manifest.json` hashes. ([experiments.md](experiments.md))
- Default linear controller SPRT vs baseline at 100 ms was **inconclusive** (long run stayed inconclusive). Do not promote on a tiny point estimate.
- Magic/PEXT slider tables: `rook_attacks_bb` was ~15% exclusive; perft(6) 2143 ms → 1765 ms. ([measurement.md](measurement.md))
- `kernel.perf_event_paranoid=4` blocks unprivileged `perf`; Callgrind is the fallback.
- HalfKP/KAT promotion requires ≥50k labeled samples (`--minimum-samples`).
- Trinomial SPRT JSON cannot be `--resume`d into the pentanomial runner.
