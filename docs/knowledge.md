# Lab knowledge

Compiled findings from NSCE experiments. Raw match logs stay under
`experiments/YYYYMMDD_*/`. This file is the **working model**: what is frozen,
what has been measured, what failed, and what to try next.

| Field | Value |
| --- | --- |
| Last updated | 2026-08-14 (SF 25k 768: MAE pass, equal-node N=400 fail +21 ± 13 to baseline) |
| Engine | NSCE 0.10 |
| Frozen baseline | `tools/configs/baseline.uci` — `EvalFile=internal`, `UseExtras=true`, `UseSearchController=false`, `UsePolicy=false`, Hash 16 |
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

- Eval: HCE-distilled `768×128×1` (`EvalFile=internal`) **plus** classical `extras()` (mobility, files, outposts, hanging, king). `UseExtras=true` is **load-bearing** on this net: turning it off lost SPRT. Keep extras on the 768 path; keep extras off for king-bucket nets.
- King-bucket nets (KAT / HalfKP): **`extras()` off**. The residual fights the net and biases learning.
- Search: PVS, TT, LMR, NMP with verify, RFP, razoring, futility, LMP, ProbCut, IIR, singular extensions (double SE on PV only), continuation 1/2/4/6, pick-next, QS fail-soft, quiet SEE, Lazy SMP. Ablation flags freeze each of these in `baseline.uci`. Hash stays **16 MB**. Iterative-deepening still stops a new iteration when remaining `< last_iter / 2` (stricter soft-stop was a coin flip).
- Policy and search controller: **off** on the frozen baseline.

### Measurement pitfalls (paid for in lab time)

- **N=20** Elo intervals on the SF ladder are too wide to promote. Use **N≥40** (paired colors). Equal-node self-play at 25k nodes is ~1 s/game here: **N=40 is still too wide** (±50 Elo, ~80% draws). Use **N≥200** (or SPRT) for that gate.
- Stockfish has no `status`. The oracle must always be **NSCE**. Otherwise `bestmove 0000` after mate aborts the match ([20260813_sf18_1600](../experiments/20260813_sf18_1600/report.md)).
- Pair-level pentanomial LLR with near-zero empirical variance explodes after one opening pair. Floor per-pair variance at **0.04** and do not accept H0/H1 before **`--min-games 40`**. A 2-game H1 is invalid ([20260813_controller_fitted](../experiments/20260813_controller_fitted/report.md)).
- Do not compare holdout MAE across different corpora (120k vs 1M). The 1M holdout is harder.
- `movetime < 50 ms` is exploratory; `sprt.py` refuses it unless `--allow-short-tc`.
- Do not compare reports unless engine / config / opening hashes match (`manifest.json`).
- After an nps/clock speedup, **equal-time SPRTs are stale**; equal-node results are not. Re-run the timed gate before promoting. Binary-vs-binary matches use `sprt.py --engine-b` (same UCI on both sides).

### Eval (KAT)

- `NSCEKAT1`: 32 horizontally-mirrored king buckets × 768, PS factorization folded at export, 12-dim dense threat residual. MIT-clean.
- Holdout MAE on 1M Lichess evals plateaus around **114 cp** at 16 epochs (hidden 128, batch 512, lr 4e-4). Target ~70 cp was not reached. **Do not raise `kHidden` until MAE stops falling with more data.**
- At **equal nodes** (25k/move, N=20) 8-epoch Lichess KAT vs internal is a coin flip (4-12-4). At **equal time** (100 ms) it loses SPRT, including **after** the 2× timed-node speedup (H0 13-51-52, score 0.332). The failure mode is a **bushier tree / less effective depth**, not inference cost. Do **not** replay `kat_candidate.bin` at 100 ms.
- NSCE self-distill (200k FENs, teacher `go nodes 25000`, same holdout as the trainers): from-scratch **768×128** is **worse** than internal (engine MAE 84.8 vs 65.1). Fine-tune from internal HCE weights on the same JSONL is still worse (**72.3 vs 65.1**, −7.2 cp). **KAT** on the same labels **beats** internal MAE (58.1 vs 65.1, +6.9 cp) but **loses equal-node N=40** (baseline 17-22-1, score 0.700, +147 ± 71). Better MAE on search-cp is not a search-Elo gate. Do not SPRT `kat_nsce25k.bin` or `nnue_nsce25k_ft.bin`. Do not compare these MAE numbers to the 114 cp Lichess holdout.
- Stockfish teacher on the **same 200k FENs** (`go nodes 25000`, extras off, `--init internal`): engine MAE **113.0 vs internal+extras 143.6** (+30.5 cp, +21%). Holdout is SF search-cp, not NSCE 65.1. Equal-node 25k **N=400** (seed 20260814): baseline **43-338-19**, score 0.530, **+21 ± 13**. Candidate score 0.470. N=40 was +17 ± 50 (exploratory). Pruning-off N=400 is the same sign (+17 ± 14). Depth-10 totals 0.47× nodes (Kiwipete-dominated; startpos 2.20× bushier). Candidate is *faster* (no extras). Do not SPRT `nnue_sf25k.bin`. ([sf25k 768](../experiments/20260814_sf25k_768_nodes400/report.md))
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
| Re-SPRT the same KAT net after 2× nps | Faster inference did not flip equal-time | H0 13-51-52, 116 games, score 0.332 ([kat_sprt_2x](../experiments/20260813_kat_sprt_2x/report.md)) |
| `UseExtras=false` on the frozen 768 net | extras() is load-bearing here (unlike KAT) | H0 3-87-36, 126 games, score 0.369 ([extras_off_sprt](../experiments/20260813_extras_off_sprt/report.md)) |
| Hash 32 at 100 ms | Mostly draws; no ±5 Elo | Inconclusive 19-168-13, LLR +0.54, 200 games ([hash32_sprt](../experiments/20260813_hash32_sprt/report.md)) |
| ID stop when remaining `< last_iter` (was `/ 2`) | Coin flip; reverted | Inconclusive 20-161-19, LLR +0.09, 200 games ([tm_sprt](../experiments/20260813_tm_sprt/report.md)) |
| More epochs on the same 1M set | MAE flat after epoch 11 | Train history in `nets/kat_candidate.metrics.json` |
| From-scratch 768 on 200k NSCE 25k-node labels | Engine MAE 84.8 vs internal 65.1 | [nsce25k 768](../experiments/20260814_nsce25k_768_train/report.md) |
| Fine-tune 768 from internal on the same 200k | Engine MAE 72.3 vs 65.1; no equal-node | [nsce25k 768 ft](../experiments/20260814_nsce25k_768_ft/report.md) |
| Promote / SPRT `kat_nsce25k.bin` | MAE +6.9 cp vs internal; equal-node N=40 score 0.300 | [nsce25k KAT](../experiments/20260814_nsce25k_kat_nodes/report.md) |
| Promote / SPRT `nnue_sf25k.bin` | MAE +30.5 cp vs SF labels; equal-node N=400 score 0.470, +21 ± 13 to baseline | [sf25k nodes400](../experiments/20260814_sf25k_768_nodes400/report.md) |
| Treat N=40 equal-node 25k as a gate | ±50 Elo, ~80% draws; N=400 flipped “coin flip” into a loss | [nodes](../experiments/20260814_sf25k_768_nodes/report.md) vs [nodes400](../experiments/20260814_sf25k_768_nodes400/report.md) |
| Label 500k more for this KAT | MAE already beat internal; equal-node still lost | Same report |
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

The 2026-08-13 evening speedups (**KAT madd inference** + **latched time-up / less clock overhead**) roughly **double nodes in 200–700 ms searches**. Converting that 2× into Elo via the same KAT net, extras-off, Hash 32, or a stricter ID stop **failed or was a coin flip**. Do not skip to a later item to “try something.”

1. **SF-teacher 768 is closed.** MAE passed; equal-node N=400 lost (+21 ± 13 to baseline). Same sign with RFP/razor/futility off. Do not SPRT, do not raise `kHidden` on this net, do not replay at 100 ms.
2. **NSCE self-distill 200k stays closed**. From-scratch MAE 84.8; fine-tune 72.3; KAT MAE win / equal-node loss.
3. **768 hidden width ≠ 128** still waits on a 768×128 that wins **equal-node**, not just MAE. `kHidden=128` is compile-time. One width per SPRT.
4. **SF18 Elo 2000, N≥40** only after a **promoted** eval. Unrestricted SF still later.

Still not next: replay `kat_candidate.bin`, `kat_nsce25k.bin`, `nnue_nsce25k_ft.bin`, or `nnue_sf25k.bin` at 100 ms, extras-off on the frozen 768, Hash 32 at 100 ms, another ID/TM constant at 100 ms (fail-low extra budget unmeasured), more ProbCut/IIR/SE constants, hidden 256 at 1M, another N=20 ladder, controller clamp relax, policy on KAT before an eval H1, 5M Lichess, 500k more labels for this KAT or this SF 768.

---

## Findings log

### 2026-08-14

- NSCE teacher `go nodes 25000` on 200k existing FENs → `train/data/nsce_nodes25k.jsonl` (0 null scores). Holdout N=20039 vs those labels, not vs Lichess 114 cp.
- From-scratch 768×128 (`nnue_nsce25k.bin`, extras on): engine MAE **84.8 vs internal 65.1** (−30%). No 500k, no equal-node. ([nsce25k 768](../experiments/20260814_nsce25k_768_train/report.md))
- Fine-tune 768 from internal (`nnue_nsce25k_ft.bin`, `--init internal`, extras on): engine MAE **72.3 vs 65.1** (−11%). Better than from-scratch, still a fail. No equal-node. ([nsce25k 768 ft](../experiments/20260814_nsce25k_768_ft/report.md))
- KAT on the same JSONL (`kat_nsce25k.bin`, extras off): engine MAE **58.1 vs 65.1** (+6.9 cp). Equal-node 25k, N=40, seed 20260814: baseline **17-22-1**, score 0.700, +147 ± 71. KAT score 0.300. No SPRT. `baseline.uci` unchanged. ([nsce25k KAT](../experiments/20260814_nsce25k_kat_nodes/report.md))
- Stockfish teacher `go nodes 25000` on the same 200k FENs → `train/data/sf18_nodes25k.jsonl` (0 null scores, sha256 `99c6a7a0…`).
- 768×128 from internal (`nnue_sf25k.bin`, extras off): engine MAE **113.0 vs internal+extras 143.6** (+21%). MAE gate pass. ([sf25k 768 train](../experiments/20260814_sf25k_768_train/report.md))
- Equal-node 25k, N=40, seed 20260814: baseline **5-32-3**, +17 ± 50 (exploratory). ([sf25k nodes](../experiments/20260814_sf25k_768_nodes/report.md))
- Equal-node 25k, **N=400**, same seed: baseline **43-338-19**, score 0.530, **+21 ± 13**. Candidate score 0.470. No SPRT. ([sf25k nodes400](../experiments/20260814_sf25k_768_nodes400/report.md))
- Same match with RFP/razor/futility off, N=400: baseline **44-332-24**, +17 ± 14. ([sf25k noprune400](../experiments/20260814_sf25k_768_noprune400/report.md))
- Depth-10 prune_diag: candidate 0.47× nodes / 1.38× nps; startpos 2.20× bushier; Kiwipete 0.14×. ([sf25k prune](../experiments/20260814_sf25k_768_prune/report.md))

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
- Inference/search speed: KAT madd + inlined attacks (`0cb7276`); latched time-up and less per-move clock (`6c94fbb`). Timed searches (~200–700 ms) search about **2× nodes**. Equal-time KAT/controller SPRTs from earlier today are **stale**; equal-node 4-12-4 is not.
- KAT 1M×16 re-SPRT after 2× nps: **H0** 13-51-52, 116 games, 100 ms, score 0.332. Faster inference did not flip equal-time. Do not replay this net at 100 ms. ([kat_sprt_2x](../experiments/20260813_kat_sprt_2x/report.md))
- `UseExtras=false` on frozen 768: **H0** 3-87-36, 126 games, 100 ms, score 0.369. extras() is load-bearing on the distilled net. Keep `UseExtras=true` on baseline. ([extras_off_sprt](../experiments/20260813_extras_off_sprt/report.md))
- Hash 32 vs 16: **inconclusive** 19-168-13, 200 games, LLR +0.54, score 0.515. Keep Hash 16. ([hash32_sprt](../experiments/20260813_hash32_sprt/report.md))
- ID stop remaining `< last_iter` (was `/ 2`): **inconclusive** 20-161-19, 200 games, LLR +0.09, score 0.503. Not promoted; one-liner reverted. ([tm_sprt](../experiments/20260813_tm_sprt/report.md))

### 2026-08-02 (historical; some `experiments/20260802_*` trees may be absent locally)

- Lab protocol: paired openings, pentanomial SPRT, ablation matrix, `manifest.json` hashes. ([experiments.md](experiments.md))
- Default linear controller SPRT vs baseline at 100 ms was **inconclusive** (long run stayed inconclusive). Do not promote on a tiny point estimate.
- Magic/PEXT slider tables: `rook_attacks_bb` was ~15% exclusive; perft(6) 2143 ms → 1765 ms. ([measurement.md](measurement.md))
- `kernel.perf_event_paranoid=4` blocks unprivileged `perf`; Callgrind is the fallback.
- HalfKP/KAT promotion requires ≥50k labeled samples (`--minimum-samples`).
- Trinomial SPRT JSON cannot be `--resume`d into the pentanomial runner.
