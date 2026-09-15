# Lab knowledge

Compiled findings from NSCE experiments. Raw match logs stay under
`experiments/YYYYMMDD_*/`. This file is the **working model**: what is frozen,
what has been measured, what failed, and what to try next.

| Field | Value |
| --- | --- |
| Last updated | 2026-09-15 evening (broken 60-ply instrument; full-game fastchess; unrestricted SF18 0-1-99; see [handoff.md](handoff.md)) |
| Engine | NSCE 0.10 |
| Frozen baseline | `tools/configs/baseline.uci` — `EvalFile=nets/nnue_search_leaves40k_rw0.bin`, extras on, policy/controller off, Hash 16, `EvalScale=1000`. Binary frozen as `build/nsce-frozen-20260915`. Vs unrestricted SF18 at 100 ms, full games: **0-1-99** (> 900 Elo behind). Vs internal net, same instrument: **123-33-44**, **+145 ± 45**. Limited SF18 Elo 2200 is a `UCI_Elo` handicap, not a rating. Previous internal arbiter: `tools/configs/baseline_internal.uci`. |
| Protocol | [hypothesis.md](hypothesis.md), [eval_pipeline.md](eval_pipeline.md), [experiments.md](experiments.md), [measurement.md](measurement.md). **Elo instrument since 2026-09-15: `tools/fastchess_match.py`** (full games, adjudication, 14 concurrent, pentanomial). |

> **Read first (2026-09-15).** Until this date every Elo gate here was run by
> `ablation_match.py` / `sprt.py` with `--max-plies 60`, scoring the truncated
> game as a draw. 175–180 of each 200 equal-node games ended that way. Those
> gates could only see effects that mate or reach ±800 cp inside 30 moves, so
> every "coin flip" / "±15" verdict below is **uninformative**, not negative.
> The same promoted-vs-internal comparison recorded here as +23 ± 9 (SPRT,
> 490 games) is **+145 ± 45** with full games (123-33-44, N=200,
> [report](../experiments/20260915_instrument_internal_full/report.md)).
> Older entries are kept unedited per the log rule; [handoff.md](handoff.md)
> lists which ones to re-measure.

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

- The north star is **equal-compute Stockfish latest** (same threads, TC, hash). Limited `UCI_Elo` is a handicap rung, not a rating and not the weekly KPI. ([hypothesis.md](hypothesis.md), [handoff.md](handoff.md))
- Elo lives in the **evaluator's data**, not in hand-tuned search constants. The promoted net is 40k search labels, a NumPy CPU trainer, and a one-sided `768×128` that still spends ~20 % of every node in `extras()`. Strong 1-person engines train ≥100 M positions on a dual-perspective net. The gap vs unrestricted SF18 is **> 900 Elo** (0-1-99 at 100 ms, full games).
- Until 2026-09-15 every Elo gate used `ablation_match.py` / `sprt.py` with `--max-plies 60`, scoring truncated games as draws (~90 % of equal-node games). Those "coin flip ±15" verdicts are **uninformative**, not negative. Elo claims now come from `tools/fastchess_match.py` (full games). The same promoted-vs-internal comparison is **+145 ± 45** (123-33-44, N=200), not the old SPRT +23 ± 9.
- Compete on **Elo/time** and **Elo/node**, not by cloning SFNNv13 or copying GPL search. Labels (cp / WDL) are allowed; Stockfish `.nnue` weights are not. Teacher cp is converted through **that teacher's** WDL curve into the **NSCE search coin** before it touches pruning thresholds. ([eval_pipeline.md](eval_pipeline.md))
- A feature that wins **fixed nodes** and loses **fixed time** is too expensive, not “almost good.” Interpret the two matches separately. ([measurement.md](measurement.md))
- Holdout MAE (float or C++) **rejects wreckage**; it does not promote. The tree reads signs and margins, not mean error. ([eval_pipeline.md](eval_pipeline.md))
- The train → quantize → C++ **export** path can copy the frozen 768: `--init internal --epochs 0` has engine MAE **0** vs static labels and equal-node N=200 is **8-184-8** (score 0.500, +0 ± 14, identical nodes). Color-flip augmentation is not a ReLU symmetry (epoch-0 MAE 290 cp, sign accuracy 0). With `--augment none` or `mirror`, Adam stays on those notes (16 ep last-epoch MAE 0.14 / 0.33). Epoch 0 is now eligible as best. ([clone trainer](../experiments/20260814_clone_trainer/report.md))
- 64 self-play games with real results (WDL mix 0.20, 768 + extras) produce a different net (C++ MAE 27.5 vs static) that is an equal-node **coin flip** (14-172-14, +0 ± 18). 256 games, both colors, stay a near-clone (C++ MAE 8.1) and still a coin flip (9-183-8, +2 ± 14). Search leaves from those finished games (4.6M unique, 20k labeled with a **copied** game result) are also a coin flip (11-172-17, candidate score 0.515, **−10 ± 18** to baseline). After fixing provenance, 80k honest search leaves plus 21 705 path WDL is still a coin flip (12-175-13, **−2 ± 17**, C++ MAE 3.09). Scaling to 160k honest leaves plus 84 043 path WDL after 1024 games is the same (17-168-15, **+3 ± 19**, C++ MAE 3.85, candidate 0.495). After 2048 games, 320k leaves plus 167 991 path WDL is still a coin flip (10-181-9, **+2 ± 15**, C++ MAE 6.90, candidate 0.498). After 4096 games, 640k leaves plus 363 091 path WDL is the same (12-181-7, **+9 ± 15**, C++ MAE 5.17, candidate 0.488). Not a companion. Do not scale `--label static` further. ([wdl games](../experiments/20260814_wdl_games/report.md), [wdl colors](../experiments/20260814_wdl_colors/report.md), [wdl leaves](../experiments/20260814_wdl_leaves/report.md), [80k leaves](../experiments/20260827_wdl_leaves80k/report.md), [160k leaves](../experiments/20260827_wdl_leaves160k/report.md), [320k leaves](../experiments/20260829_wdl_leaves320k/report.md))
- `Elo/nodo` is diagnostic only: pruning changes what a node means.

### Frozen baseline (promoted 768)

- Eval: search-teacher 40k@8000, result-weight 0, `768×128×1` (`EvalFile=nets/nnue_search_leaves40k_rw0.bin`) **plus** classical `extras()`. Full-game vs internal: **123-33-44**, **+145 ± 45**. Old 60-ply SPRT H1 (+23 ± 9) understated that. Keep extras on this 768 path; extras-off lost SPRT on the previous internal net (decisive 60-ply H0, not a coin flip). Previous arbiter: `tools/configs/baseline_internal.uci` (`EvalFile=internal`).
- Strength: **> 900 Elo behind** unrestricted SF18 at 100 ms, 1 thread, Hash 16, full games (**0-1-99**). Limited SF18 `UCI_Elo=2200` (N=200, 67-88-45, +38 ± 36) is a handicap match, not this engine's rating.
- King-bucket nets (KAT / HalfKP): **`extras()` off**. The residual fights the net and biases learning. KAT on this mix lost equal-node **111-87-2** (decisive even on the blind gate).
- Search: PVS, TT, LMR, NMP with verify, RFP, razoring, futility, LMP, ProbCut, IIR, singular extensions (double SE on PV only), continuation 1/2/4/6, pick-next, QS fail-soft, quiet SEE, Lazy SMP. Hash stays **16 MB**. `EvalScale` stays **1000** until a full-game gate says otherwise (P0.2). Blanket check extension stays (SPRT [0, 10] N=3000 inconclusive). Iterative-deepening still stops a new iteration when remaining `< last_iter / 2`.
- Policy and search controller: **off** until P0.2 re-measures them with full games.

### Measurement pitfalls (paid for in lab time)

- **The 60-ply gate was blind.** `ablation_match.py` / `sprt.py` stop at `--max-plies 60` and count those games as draws. ~90 % of equal-node gates ended that way, so almost every "coin flip ±15" could not see real Elo. Use `tools/fastchess_match.py` (full games, resign/draw adjudication). Keep the old runners for node/time telemetry only.
- **N=20** Elo intervals on the SF ladder are too wide to promote. Use **N≥40** (paired colors). Equal-node self-play at 25k nodes is ~1 s/game here: **N=40 is still too wide** (±50 Elo, ~80% draws). Use **N≥200** (or SPRT) for that gate. Limited SF18 Elo 2200 at N=40 and N=80 both included 0; N=200 is the claim-quality *handicap* sample, not a rating.
- Stockfish has no `status`. The oracle must always be **NSCE**. Otherwise `bestmove 0000` after mate aborts the match ([20260813_sf18_1600](../experiments/20260813_sf18_1600/report.md)).
- Pair-level pentanomial LLR with near-zero empirical variance explodes after one opening pair. Floor per-pair variance at **0.04** and do not accept H0/H1 before **`--min-games 40`**. A 2-game H1 is invalid ([20260813_controller_fitted](../experiments/20260813_controller_fitted/report.md)).
- Do not compare holdout MAE across different corpora (120k vs 1M). The 1M holdout is harder.
- `movetime < 50 ms` is exploratory; `sprt.py` refuses it unless `--allow-short-tc`.
- Do not compare reports unless engine / config / opening hashes match (`manifest.json`).
- After an nps/clock speedup, **equal-time SPRTs are stale**; equal-node results are not. Re-run the timed gate before promoting. Binary-vs-binary matches use `sprt.py --engine-b` (same UCI on both sides).
- PATH `stockfish` on this machine is **Stockfish 17** (2024-09-06). Reports through 2026-08-13 that say "SF18" used that binary. Pin official SF18 and current-dev with `tools/freeze_targets.py`; do not let PATH change the target.

### Eval (KAT)

- `NSCEKAT1`: 32 horizontally-mirrored king buckets × 768, PS factorization folded at export, 12-dim dense threat residual. MIT-clean.
- Holdout MAE on 1M Lichess evals plateaus around **114 cp** at 16 epochs (hidden 128, batch 512, lr 4e-4). Target ~70 cp was not reached. **Do not raise `kHidden` until MAE stops falling with more data.**
- At **equal nodes** (25k/move, N=20) 8-epoch Lichess KAT vs internal is a coin flip (4-12-4). At **equal time** (100 ms) it loses SPRT, including **after** the 2× timed-node speedup (H0 13-51-52, score 0.332). The failure mode is a **bushier tree / less effective depth**, not inference cost. Do **not** replay `kat_candidate.bin` at 100 ms.
- NSCE self-distill (200k FENs, teacher `go nodes 25000`, same holdout as the trainers): from-scratch **768×128** is **worse** than internal (engine MAE 84.8 vs 65.1). Fine-tune from internal HCE weights on the same JSONL is still worse (**72.3 vs 65.1**, −7.2 cp). **KAT** on the same labels **beats** internal MAE (58.1 vs 65.1, +6.9 cp) but **loses equal-node N=40** (baseline 17-22-1, score 0.700, +147 ± 71). Better MAE on search-cp is not a search-Elo gate. Do not SPRT `kat_nsce25k.bin` or `nnue_nsce25k_ft.bin`. Do not compare these MAE numbers to the 114 cp Lichess holdout.
- Stockfish teacher on the **same 200k FENs** (`go nodes 25000`, extras off, `--init internal`): engine MAE **113.0 vs internal+extras 143.6** (+30.5 cp, +21%). Holdout is SF search-cp, not NSCE 65.1. Equal-node 25k **N=400** (seed 20260814): baseline **43-338-19**, score 0.530, **+21 ± 13**. Candidate score 0.470. N=40 was +17 ± 50 (exploratory). Pruning-off N=400 is the same sign (+17 ± 14). Affine `EvalScale` 1091/1519 still loses N=200 (+26 / +28). Depth-10 totals 0.47× nodes (Kiwipete-dominated; startpos 2.20× bushier). Candidate is *faster* (no extras). Do not SPRT `nnue_sf25k.bin`. ([sf25k 768](../experiments/20260814_sf25k_768_nodes400/report.md), [evalscale](../experiments/20260814_evalscale_nodes/report.md))
- 120k-corpus MAE 102 cp is not comparable to the 1M holdout.

### Search controller

- Default prior (`NSCECTRL`, `bias=-120`) and fitted `NSCECTL2` (hist, improving, cut_node, SEE) are both **unpromoted**. Clamp stays **[-1, +2]**.
- Fitted weights from 246k self-search LMR events: `w_cut=-11` dominates; `w_see=0`. Ridge MAE 14.4 on the residual. Equal-time SPRT slightly negative / inconclusive.
- Without research/cutoff labels there is nothing useful to learn. Log LMR with `TelemetryFile` while the controller is **off**.
- Re-fit only on the **winning** eval baseline (this promoted 768), never mix KAT + controller in one SPRT.

### Policy

- Piece→to + from→to is too weak to beat history (lost equal-node on this 768). Conditioning a destination head on the KAT accumulator stays closed: king-relative without threats already lost equal-node.

---

## Rejected / do-not-repeat

Rows whose evidence is a 60-ply "coin flip ±15" are **uninformative**, not
negative. Re-measure those under P0.2 in [handoff.md](handoff.md). Signs that
still stand: KAT 111-87-2, SF-teacher 768 N=400, extras-off H0, staged
MovePicker **−48 ± 31** full games. Do not drop the blanket check extension
(SPRT N=3000 inconclusive).

| Idea | Why it is closed | Evidence |
| --- | --- | --- |
| Promote KAT 1M×8 | Lost equal-time SPRT | H0 39-112-85, 236 games, 100 ms ([kat_sprt](../experiments/20260813_kat_sprt/report.md)) |
| Promote KAT 1M×16 | MAE only 117→114; still losing | Inconclusive 36-86-78, LLR −2.11, 200 games ([kat_e16_sprt](../experiments/20260813_kat_e16_sprt/report.md)) |
| Re-SPRT the same KAT net after 2× nps | Faster inference did not flip equal-time | H0 13-51-52, 116 games, score 0.332 ([kat_sprt_2x](../experiments/20260813_kat_sprt_2x/report.md)) |
| `UseExtras=false` on the frozen 768 net | extras() is load-bearing here (unlike KAT) | H0 3-87-36, 126 games, score 0.369 ([extras_off_sprt](../experiments/20260813_extras_off_sprt/report.md)) |
| Hash 32 at 100 ms | 60-ply inconclusive vs *internal*; re-measure Hash 32 on this 768 (P0.2) | Inconclusive 19-168-13, LLR +0.54, 200 games ([hash32_sprt](../experiments/20260813_hash32_sprt/report.md)) |
| ID stop when remaining `< last_iter` (was `/ 2`) | Coin flip; reverted | Inconclusive 20-161-19, LLR +0.09, 200 games ([tm_sprt](../experiments/20260813_tm_sprt/report.md)) |
| More epochs on the same 1M set | MAE flat after epoch 11 | Train history in `nets/kat_candidate.metrics.json` |
| From-scratch 768 on 200k NSCE 25k-node labels | Engine MAE 84.8 vs internal 65.1 | [nsce25k 768](../experiments/20260814_nsce25k_768_train/report.md) |
| Fine-tune 768 from internal on the same 200k | Engine MAE 72.3 vs 65.1; no equal-node | [nsce25k 768 ft](../experiments/20260814_nsce25k_768_ft/report.md) |
| Promote / SPRT `kat_nsce25k.bin` | MAE +6.9 cp vs internal; equal-node N=40 score 0.300 | [nsce25k KAT](../experiments/20260814_nsce25k_kat_nodes/report.md) |
| Promote / SPRT `nnue_sf25k.bin` | MAE +30.5 cp vs SF labels; equal-node N=400 score 0.470, +21 ± 13 to baseline | [sf25k nodes400](../experiments/20260814_sf25k_768_nodes400/report.md) |
| `EvalScale=511` on frozen baseline | SF-label origin scale; equal-node N=200 coin flip | [evalscale](../experiments/20260814_evalscale_nodes/report.md) |
| Affine-scale `nnue_sf25k.bin` (1091 / 1519) | Still loses equal-node N=200 (+26 / +28 Elo to baseline) | [evalscale](../experiments/20260814_evalscale_nodes/report.md) |
| Train Stockfish cp and prune with NSCE thresholds | Wrong currency; affine scale did not fix it | Same + [eval_pipeline.md](eval_pipeline.md) |
| Promote on float/C++ MAE | Better exam, worse partner, twice | nsce25k KAT MAE +6.9 then N=40 score 0.300; sf25k MAE +21% then N=400 score 0.470 |
| Treat N=40 equal-node 25k as a gate | ±50 Elo, ~80% draws; N=400 flipped “coin flip” into a loss | [nodes](../experiments/20260814_sf25k_768_nodes/report.md) vs [nodes400](../experiments/20260814_sf25k_768_nodes400/report.md) |
| Label 500k more for this KAT | MAE already beat internal; equal-node still lost | Same report |
| Raise hidden to 256 at 120k–1M | Memorizes; MAE still data-limited | 16-epoch plateau at 114 cp |
| HCE `extras()` on top of KAT/HalfKP | Residual fights the net | Gated in `evaluate()` when `uses_king_buckets()` |
| Promote fitted LMR controller | Slightly negative equal-time | Inconclusive 23-143-34, LLR −0.99 ([controller_sprt](../experiments/20260813_controller_sprt/report.md)) |
| Relax controller clamp before Elo/nodo rises | Current ±1 ply already does not help | Same SPRT |
| Color-flip augmentation on the 768 ReLU net | Not odd (`w1` all +); epoch-1 MAE 33.7 vs 0.06 with `--augment none` | [clone trainer](../experiments/20260814_clone_trainer/report.md) |
| 64 self-play games + WDL result-weight 0.20 as an eval candidate | Equal-node N=200 is 14-172-14, +0 ± 18 | [wdl games](../experiments/20260814_wdl_games/report.md) |
| 256 both-color self-play paths, same WDL mix | Near-clone (C++ MAE 8.1); equal-node 9-183-8, +2 ± 14 | [wdl colors](../experiments/20260814_wdl_colors/report.md) |
| 20k search leaves stamped with those game results | C++ MAE 12.9; equal-node 11-172-17, −10 ± 18 (candidate 0.515) | [wdl leaves](../experiments/20260814_wdl_leaves/report.md) |
| 80k honest search leaves + path WDL | C++ MAE 3.09; equal-node 12-175-13, −2 ± 17 | [80k leaves](../experiments/20260827_wdl_leaves80k/report.md) |
| 160k honest search leaves + 84k path WDL | C++ MAE 3.85; equal-node 17-168-15, +3 ± 19 | [160k leaves](../experiments/20260827_wdl_leaves160k/report.md) |
| 320k honest search leaves + 168k path WDL | C++ MAE 6.90; equal-node 10-181-9, +2 ± 15 | [320k leaves](../experiments/20260829_wdl_leaves320k/report.md) |
| 640k honest search leaves + 363k path WDL | C++ MAE 5.17; equal-node 12-181-7, +9 ± 15 | [640k leaves](../experiments/20260829_wdl_leaves640k/report.md) |
| Relabel the 40k search mix at `go nodes 25000` | Equal-node 6-180-14, −14 ± 15 (candidate 0.520); weaker than 8000-node mix | [search 40k n25k](../experiments/20260903_search_leaves40k_n25k/report.md) |
| Double the 8000-node search mix to 80k+80k | Equal-node 9-173-18, −16 ± 18 (candidate 0.523); weaker than 40k mix | [search 80k](../experiments/20260903_search_leaves80k/report.md) |
| 80k@8000 at result-weight 0 vs promoted 40k | Equal-node 9-180-11, −3 ± 16 (candidate 0.505) | [search 80k rw0](../experiments/20260904_search_leaves80k_rw0/report.md) |
| Disjoint 40k@8000 rw0 from the 8192 dump | Equal-node 10-180-10, +0 ± 15 (candidate 0.500) | [search 40k 8192](../experiments/20260909_search_leaves40k_8192/report.md) |
| 40k@8000 rw0 from appended 8192 leaves only | Equal-node 9-181-10, −2 ± 15 (candidate 0.503) | [search 40k newleaves](../experiments/20260909_search_leaves40k_newleaves/report.md) |
| Fine-tune promoted 768 on that new-leaf mix | Equal-node 5-186-9, −7 ± 13 (candidate 0.510) | [search 40k newleaves ft](../experiments/20260909_search_leaves40k_newleaves_ft/report.md) |
| KAT `--no-threats` on the promoted 40k mix | Equal-node 111-87-2, +212 ± 36 (candidate 0.228); C++ MAE vs static 138 | [kat 40k rw0](../experiments/20260909_kat_search40k_rw0/report.md) |
| `EvalScale=926` on the promoted 768 | 60-ply coin flip; re-measure P0.2 | 10-176-14, −7 ± 17 ([evalscale 926](../experiments/20260909_evalscale926/report.md)) |
| Re-fit LMR controller on the promoted 768 | 60-ply coin flip; re-measure P0.2 | 9-182-9, +0 ± 15 ([controller rw0](../experiments/20260909_controller_rw0/report.md)) |
| From-to `NSCEPOLY` on the promoted 768 | Equal-node 27-166-7, +35 ± 20 (candidate 0.450) | [policy rw0](../experiments/20260909_policy_rw0/report.md) |
| Staged MovePicker + SEE reuse (`build-nps/nsce`) | That implementation loses at equal time, full games | picker **−48 ± 31**, N=300 ([nps full](../experiments/20260915_nps_movepicker_time_full/report.md)); old 60-ply equal-node 20-170-10, +17 ± 19 |
| Drop blanket check extension | SPRT [0, 10] N=3000 inconclusive; N=600 LOS 97 % did not hold | +3.8 ± 10.2, LLR −0.44 ([no-check SPRT](../experiments/20260915_no_check_ext_sprt/report.md)) |
| Mix clone leaves into that train set and trust the holdout | Val is clone-dominated; best epoch 0 ships the clone | [wdl games](../experiments/20260814_wdl_games/report.md) |
| Port more Stockfish search (multi-cut, threat-input sparse nets, SFNNv13) | GPL; keeps us behind Fishtest-tuned constants | License + hypothesis |
| Train from Stockfish `.nnue` files | GPL / not our net | Labels only |
| Treat N=20 SF18 2000 (7-8-5, +35) as a win | Interval ±120; N=40 reversed the sign | [v10](../experiments/20260813_v10/report.md) vs [sf18_2000](../experiments/20260813_sf18_2000/report.md) |
| Treat N=40 or N=80 SF18 2200 as ≥2200 | Both CIs include 0; N=200 is the claim | [sf18 2200 n40](../experiments/20260903_sf18_2200_rw0/report.md), [n80](../experiments/20260904_sf18_2200_rw0_n80/report.md), [n200](../experiments/20260909_sf18_2200_rw0_n200/report.md) |
| Use Stockfish as `status` oracle | Aborts on mate (`bestmove 0000`) | [sf18_1600](../experiments/20260813_sf18_1600/report.md) |
| Accept SPRT H1 after one opening pair | Degenerate pentanomial variance | [controller_fitted](../experiments/20260813_controller_fitted/report.md) |

---

## Ladder position

Full games (`tools/fastchess_match.py`), 100 ms, 1 thread, Hash 16,
`openings_balanced.epd`, resign/draw adjudication.

| Opponent | N | W-D-L (NSCE) | Elo ±95% | Notes |
| --- | ---: | ---: | ---: | --- |
| Internal net (`baseline_internal.uci`) | 200 | **123-33-44** | **+145 ± 45** | [instrument](../experiments/20260915_instrument_internal_full/report.md) |
| Unrestricted SF18 | 100 | **0-1-99** | **> 900 behind** | [sf18 unlimited](../experiments/20260915_sf18_unlimited_100ms/report.md) |

`UCI_Elo` handicap rungs (old Python harness, 60-ply draws) are **not** a
rating. Historical table kept below.

| Opponent | N | W-D-L (NSCE) | Score | Elo ±95% | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| SF18 Elo 1400 (v0.9) | 20 | 11-6-3 | 0.700 | +147 ± 146 | [sf18_1400](../experiments/20260813_sf18_1400/report.md) |
| SF18 Elo 1400 (v0.10) | 20 | 19-0-1 | 0.950 | +512 ± 1888 | Exploratory N |
| SF18 Elo 1600 (v0.10) | 20 | 15-2-3 | 0.800 | +241 ± 234 | Exploratory N |
| SF18 Elo 1800 (v0.10) | 20 | 8-9-3 | 0.625 | +89 ± 118 | Exploratory N |
| SF18 Elo 2000 (v0.10) | 20 | 7-8-5 | 0.550 | +35 ± 120 | **Superseded** |
| SF18 Elo 2000 (v0.10 internal) | 40 | 11-13-16 | 0.438 | −44 ± 90 | Pre-promotion |
| SF18 Elo 2000 (rw0, limited) | 40 | 25-8-7 | 0.725 | +168 ± 114 | Handicap rung |
| SF18 Elo 2200 (v0.10 internal) | 40 | 10-17-13 | 0.463 | −26 ± 82 | Pre-promotion |
| SF18 Elo 2200 (rw0, limited) | 40 | 17-14-9 | 0.600 | +70 ± 90 | CI includes 0 |
| SF18 Elo 2200 (rw0, limited) | 80 | 30-25-25 | 0.531 | +22 ± 64 | CI includes 0 |
| SF18 Elo 2200 (rw0, limited) | 200 | 67-88-45 | 0.555 | +38 ± 36 | Handicap; not a rating |

Historical rungs through 2026-08-13 used PATH Stockfish 17.

Self-play: NSCE 0.9 vs 0.8 at 100 ms / 60 plies was 2-36-2 (almost all `max_plies` draws) — indecisive; that is the same broken instrument.

---

## Next levers

Order is [handoff.md](handoff.md). Do not skip P0.2 to start datagen.

1. **P0.2 — re-measure leftover 60-ply coin-flips with fastchess** (`--st 100 --rounds 300`): `EvalScale=926`, Hash 32 on this 768, `controller_rw0`, 40k λ=0.20, 80k rw0, 640k static. Annotate Rejected; do not delete old rows.
2. **P0.3 / P0.4** — KPI vs `build/nsce-frozen-20260915` at 8+0.08; larger UHO book.
3. **P1** — `nsce_datagen` ≥100 M bulletformat positions + bullet trainer + `(768→512)×2` SCReLU (`NSCEPER1`). Then `UseExtras=false` measured, not assumed. Gen1 after H1.
4. **P2** — SPSA (`NSCE_TUNE` + weather-factory), not hand-tuned constants. Staged picker rewritten from scratch; do not revive `build-nps/nsce`.
5. Clone-export and deployed-integer gates still apply. Do not scale `--label static`. Do not raise `result-weight` on the 40k mix as the Elo path.

Closed and not next: SF-teacher 768, NSCE self-distill 200k, replay KAT bins, extras-off on this 768, drop the check extension, `UCI_Elo` as a rating, GPL search / Stockfish `.nnue` weights, king buckets / hidden 1024 / threats before P1 gen1, Lazy SMP at 1-thread KPI. Richer features on nets that already lose stay out.

---

## Findings log

### 2026-09-15

- Instrument: `ablation_match.py` / `sprt.py` `--max-plies 60` scores truncated games as draws (~90 % of equal-node gates). Elo claims now from `tools/fastchess_match.py` (full games). Promoted 768 vs internal, 100 ms, N=200: **123-33-44**, **+145 ± 45** (old SPRT said +23). Decision: diagnostic of the gate. ([instrument](../experiments/20260915_instrument_internal_full/report.md))
- Promoted 768 vs unrestricted SF18, 100 ms, N=100, full games: **0-1-99**, > 900 Elo behind. North star is this gap, not `UCI_Elo` 2200. ([sf18 unlimited](../experiments/20260915_sf18_unlimited_100ms/report.md))
- Frozen vs staged-MovePicker `build-nps/nsce`, 100 ms, N=300, full games: frozen **134-73-93**, picker **−48 ± 31**. That implementation still loses. ([nps full](../experiments/20260915_nps_movepicker_time_full/report.md))
- Drop blanket check extension: N=600 candidate **+23 ± 23**; SPRT [0, 10] N=3000 **inconclusive** LLR −0.44, **+3.8 ± 10.2**. Keep the extension. ([N=600](../experiments/20260915_no_check_ext/report.md), [SPRT](../experiments/20260915_no_check_ext_sprt/report.md))
- Limited SF18 Elo 2200 N=200 is a handicap rung, not a rating: **67-88-45**, **+38 ± 36**, N=200, TC=100 ms, seed=20260814 (`experiments/20260909_sf18_2200_rw0_n200`). Superseded as a strength claim by unrestricted 0-1-99.

### 2026-09-09

- King-relative HalfKA-hm `--no-threats` on the promoted 40k@8000 mix, result-weight 0, extras off (`nets/kat_search_leaves40k_rw0.bin`). Equal-node 25k N=200 seed 20260814: baseline **111-87-2**, score 0.773, **+212 ± 36**. Candidate 0.228. Deployed C++ MAE vs frozen static **138**. No SPRT. Do not promote. Do not add the 12-threat residual on this loser. ([kat 40k rw0](../experiments/20260909_kat_search40k_rw0/report.md))
- Affine `EvalScale=926` on the promoted 768 (holdout origin 0.926 vs frozen internal static). Equal-node 25k N=200 seed 20260814: baseline **10-176-14**, score 0.490, **−7 ± 17**. Candidate 0.515. Interval includes 0. No SPRT. Keep `EvalScale=1000`. ([evalscale 926](../experiments/20260909_evalscale926/report.md))
- LMR controller re-fit on the promoted 768 (`nets/controller_rw0.bin`, 267 333 events, `w_cut=-9`). Equal-node 25k N=200 seed 20260814: baseline **9-182-9**, score 0.500, **+0 ± 15**. Candidate 0.500. No SPRT. Keep `UseSearchController=false`. ([controller rw0](../experiments/20260909_controller_rw0/report.md))
- From-to policy (`nets/policy_rw0.bin`) from 256 self-play games with the promoted 768 (65-61-43 + 87 unfinished). Equal-node 25k N=200 seed 20260814: baseline **27-166-7**, score 0.550, **+35 ± 20**. Candidate 0.450. No SPRT. Keep `UsePolicy=false`. ([policy rw0](../experiments/20260909_policy_rw0/report.md))
- Datagen self-play 6002→**8192** at 100 ms, 13×`Threads=1`, promoted 768: **2480-2184-1099** + 2429 unfinished (increment **589-531-307** + 763). `collect_leaves --append` skip 11809, **5480** new roots, **+36 817 302** unique leaves (24G jsonl). Path FENs **648 979**. ([datagen 8192](../experiments/20260909_datagen8192/report.md))
- Disjoint 40k@8000 rw0 mix from the enlarged dump (exclude promoted 40k keys). Equal-node 25k N=200 seed 20260814: baseline **10-180-10**, score 0.500, **+0 ± 15**. Candidate 0.500. No SPRT. Keep the promoted 40k net. ([search 40k 8192](../experiments/20260909_search_leaves40k_8192/report.md))
- 40k@8000 rw0 from **appended 8192 leaves only** (last 36.8M jsonl rows + increment path). Equal-node 25k N=200 seed 20260814: baseline **9-181-10**, score 0.498, **−2 ± 15**. Candidate 0.503. No SPRT. ([search 40k newleaves](../experiments/20260909_search_leaves40k_newleaves/report.md))
- Fine-tune the promoted 768 on that mix (`--init` the promoted bin). Equal-node 25k N=200 seed 20260814: baseline **5-186-9**, score 0.490, **−7 ± 13**. Candidate 0.510. Interval includes 0. No SPRT. ([search 40k newleaves ft](../experiments/20260909_search_leaves40k_newleaves_ft/report.md))
- Promoted eval vs pinned SF18 Elo 2200, N=200, 100 ms, seed 20260814, NSCE status: **67-88-45**, score 0.555, **+38 ± 36**. Interval excludes 0 (lower bound +2). N=40 and N=80 included 0. Wins the limited 2200 KPI. Unrestricted SF unplayed. ([sf18 2200 n200](../experiments/20260909_sf18_2200_rw0_n200/report.md))

### 2026-09-03

- 80k@8000 mix retrained at **result-weight 0** vs the promoted 40k net. Equal-node 25k N=200 seed 20260814: baseline **9-180-11**, score 0.495, **−3 ± 16**. Candidate 0.505. Interval includes 0. No SPRT. Do not promote. ([search 80k rw0](../experiments/20260904_search_leaves80k_rw0/report.md))
- Promoted eval vs pinned SF18 Elo 2200, N=80, 100 ms, seed 20260814, NSCE status: **30-25-25**, score 0.531, **+22 ± 64**. Interval includes 0. N=40 (17-14-9, +70 ± 90) did not hold. Do not record ≥2200. ([sf18 2200 n80](../experiments/20260904_sf18_2200_rw0_n80/report.md))
- Promoted eval vs pinned SF18 Elo 2200, N=40, 100 ms, seed 20260814, NSCE status: **17-14-9**, score 0.600, **+70 ± 90**. Interval includes 0. Superseded by N=80. ([sf18 2200 rw0](../experiments/20260903_sf18_2200_rw0/report.md))
- Promoted eval (`nets/nnue_search_leaves40k_rw0.bin`) vs pinned SF18 Elo 2000, N=40, 100 ms, seed 20260814, NSCE status: **25-8-7**, score 0.725, **+168 ± 114**. Interval excludes 0. Wins the 2000 KPI (old internal rung was 11-13-16, −44 ± 90). ([sf18 2000 rw0](../experiments/20260903_sf18_2000_rw0/report.md))
- Search-teacher 40k mix with **result-weight 0** (same `go nodes 8000` FENs), 768 extras on. Equal-node 25k N=200: baseline **3-177-20**, **−30 ± 16**. Equal-time SPRT **H1** at 490 games **38-447-5**, LLR **+2.97**, **+23 ± 9**. `promotion_gate --stage eval` PASS. `EvalFile` promoted; old internal arbiter at `tools/configs/baseline_internal.uci`. ([nodes](../experiments/20260903_search_leaves40k_rw0/report.md), [SPRT H1](../experiments/20260903_search_leaves40k_rw0_sprt/report.md))
- Search-teacher 80k mix (80k `search_leaf` + 80k path, `go nodes 8000`), 768 extras on, `--init internal --augment mirror`, result-weight 0.20. Best epoch 32. Float MAE vs search/WDL **181**. Deployed MAE vs frozen static **16.48**. Equal-node 25k N=200 seed 20260814: baseline **9-173-18**, score 0.477, **−16 ± 18**. Candidate 0.523. Interval includes 0. `equal_node_clearly_winning` FAIL. No SPRT. Do not scale this mix further. ([search 80k](../experiments/20260903_search_leaves80k/report.md))
- Search-teacher 40k relabeled at `go nodes 25000` (same FENs as the 8000 mix), 768 extras on, `--init internal --augment mirror`, result-weight 0.20. Best epoch 18. Float MAE vs search/WDL **202**. Deployed MAE vs frozen static **11.40** (N=6737). Equal-node 25k N=200 seed 20260814: baseline **6-180-14**, score 0.480, **−14 ± 15**. Candidate 0.520. Interval includes 0. `equal_node_clearly_winning` FAIL. No SPRT. Do not scale teacher nodes on this 40k set. ([search 40k n25k](../experiments/20260903_search_leaves40k_n25k/report.md))
- Search-teacher 40k equal-time SPRT vs frozen baseline, 100 ms, max 400, seed 20260814: **inconclusive** **19-372-9**, LLR **+0.90**, pentanomial 0-7-177-15-1, candidate 0.5125, **+9 ± 9**. `promotion_gate --stage eval` FAIL. Do not promote `EvalFile`. Equal-node had passed (7-170-23, −28 ± 19). ([search 40k SPRT](../experiments/20260902_search_leaves40k_sprt/report.md))

### 2026-09-02

- Search-teacher 40k mix (40k `search_leaf` + 40k path, `go nodes 8000`), 768 extras on, `--init internal --augment mirror`, result-weight 0.20. Best epoch 10. Float MAE vs search/WDL **188**. Deployed MAE vs frozen static **9.82** (N=6737, `--gate none`). Equal-node 25k N=200 seed 20260814: baseline **7-170-23**, score 0.460, **−28 ± 19**. Candidate 0.540. Interval excludes 0. Equal-time SPRT next; `EvalFile` not promoted. Train crash `NameError: _variant_target` after `pack_active_rows` was restored. ([search 40k](../experiments/20260902_search_leaves40k/report.md))
- Honest 640k search leaves + 363 091 path WDL after 4096 games, 768 extras on, `--init internal --augment mirror`, result-weight 0.20. C++ MAE **5.17** (N=84762), clone gate PASS. Equal-node 25k N=200 seed 20260814: baseline **12-181-7**, score 0.512, **+9 ± 15**. Candidate 0.488. `promotion_gate --stage eval` FAIL. No SPRT. Do not scale static labels further. ([640k leaves](../experiments/20260829_wdl_leaves640k/report.md))

### 2026-08-29

- Staged MovePicker + SEE reuse (`build-nps/nsce`) vs frozen `build/nsce`, same `baseline.uci`. Equal-node 25k N=200 seed 20260814: baseline **20-170-10**, score 0.525, **+17 ± 19**. Candidate 0.475. Depth-12 bench nps **865k→993k**. `promotion_gate --stage search` FAIL. No SPRT. Source reverted. ([nps movepicker](../experiments/20260829_nps_movepicker/report.md))
- Streaming datagen 2048→4096 self-play at 100 ms both colors. **1299-1119-527** + 1151 unfinished. `collect_leaves --append` skipped 5895 then crashed at 2897/2940 (disk full); remaining 44 roots **+268 762**. Increment **+19 471 553** unique leaves. ([datagen 4096](../experiments/20260829_datagen4096/report.md))
- Honest 320k search leaves + 167 991 path WDL after 2048 games, 768 extras on, `--init internal --augment mirror`, result-weight 0.20. C++ MAE **6.90** (N=40659), clone gate PASS. Equal-node 25k N=200 seed 20260814: baseline **10-181-9**, score 0.502, **+2 ± 15**. Candidate 0.498. `promotion_gate --stage eval` FAIL. No SPRT. ([320k leaves](../experiments/20260829_wdl_leaves320k/report.md))
- Streaming datagen increment: self-play 1024→2048 at 100 ms both colors. **655-572-248** + 573 unfinished (no fake draws). Remainder after 1833 used 15×1-thread workers (not SMP). `collect_leaves --append` skipped 2902 known roots, 1523 new searches, **+10 129 214** unique leaves. ([datagen 2048](../experiments/20260827_datagen2048/report.md))

### 2026-08-27

- Honest 160k search leaves + 84 043 path WDL after 1024 games, 768 extras on, `--init internal --augment mirror`, result-weight 0.20. C++ MAE **3.85** (N=21046), clone gate PASS. Equal-node 25k N=200 seed 20260814: baseline **17-168-15**, score 0.505, **+3 ± 19**. Candidate 0.495. `promotion_gate --stage eval` FAIL. No SPRT. ([160k leaves](../experiments/20260827_wdl_leaves160k/report.md))
- Streaming datagen increment: self-play 512→1024 at 100 ms both colors. **323-275-120** + 306 unfinished (no fake draws). `collect_leaves --append` skipped 1413 known roots, 741 new searches, **+4 886 429** unique leaves. ([datagen 1024](../experiments/20260827_datagen1024/report.md))
- Streaming datagen increment: self-play 256→512 at 100 ms both colors. **170-129-63** + 150 unfinished (no fake draws). `collect_leaves --append` skipped 672 known roots, 414 new searches, **+3 103 231** unique leaves. ([datagen 512](../experiments/20260827_datagen512/report.md))
- Leaf provenance: `stamp_leaf` copies game WDL only onto the search root (`label_kind=path`). Hypothetical QS/static leaves are `search_leaf` and unlabeled. Salvaged `leaves_with_results.jsonl`: 4 613 450 records, **2 336** path with result (was every leaf).
- Honest 80k search leaves + 21 705 path WDL, 768 extras on, `--init internal --augment mirror`, result-weight 0.20. C++ MAE **3.09** (N=9705), clone gate PASS. Equal-node 25k N=200 seed 20260814: baseline **12-175-13**, score 0.497, **−2 ± 17**. Candidate 0.502. `promotion_gate --stage eval` FAIL. No SPRT. ([80k leaves](../experiments/20260827_wdl_leaves80k/report.md))
- Frozen Stockfish targets refreshed: SF18 `6b087694…` unchanged; current-dev **stockfish-dev-20260825-2edd935b** (`aecdebba…`). Never PATH `stockfish`. ([frozen-targets](../experiments/frozen-targets/manifest.json))
- P0 TT-eval contract (raw in TT, correction once) vs pre-P0 binary, same `baseline.uci`. Equal-node 25k N=200 seed 20260814: pre-P0 **13-177-10**, score 0.507, **+5 ± 17**. P0 candidate score 0.493. Diagnostic coin flip; no SPRT; ships as correctness. ([tt eval raw](../experiments/20260827_tt_eval_raw/report.md))

### 2026-08-14

- Eval manufacture/judgment rewritten into a fixed 9-step order: clone the frozen static arbiter before any richer net; NSCE search coin; leaf labels; deployed C++ integers; games with results; one change + extras contract; equal-node N≥200 then equal-time; king-relative without threats only after that; search retune only for a winning eval. ([eval_pipeline.md](eval_pipeline.md))
- Clone step 1: 832k unique leaves from 64×25k searches; 20k uniform static labels. `--init internal --epochs 0` re-export: C++ MAE **0.00** (N=1987). Equal-node 25k N=200 seed 20260814: **8-184-8**, score 0.500, **+0 ± 14**, identical 386603 nodes/game. `promotion_gate --stage clone` PASS. Adam 16 ep lr 4e-4 with the old 4-way color-flip: engine MAE 35.4, FAIL. ([clone nodes](../experiments/20260814_clone_nodes/report.md))
- Clone trainer: color-flip is not odd on this ReLU 768 (epoch-0 MAE **290** cp, sign 0). `--augment none` 16 ep last-epoch MAE **0.14**; `mirror` **0.33**; `full` epoch-1 **33.7**. Epoch 0 kept as best; exported stay net sha256-identical to the clone export, C++ MAE **0.00**, clone gate PASS. ([clone trainer](../experiments/20260814_clone_trainer/report.md))
- Self-play WDL mix: 64 games 100 ms max_plies 200 → 41 mates, 9 draws, 14 unfinished (no fake 1/2). 8829 static labels, 6015 with result. Games-only 768 (`nnue_wdl.bin`, extras on): val MAE 115.6→114.1, C++ vs static **27.5** (N=744). Equal-node 25k N=200 seed 20260814: **14-172-14**, score 0.500, **+0 ± 18**. `promotion_gate --stage eval` FAIL. No SPRT. ([wdl games](../experiments/20260814_wdl_games/report.md))
- Both-color WDL mix: 256 games (128 openings × 2), 88-67-25 + 76 unfinished. 37 620 static labels, 22 344 with result. `nnue_wdl_colors.bin`: best epoch 8, C++ MAE **8.06** (N=3283), clone gate PASS, affine 1.00. Equal-node 25k N=200 seed 20260814: **9-183-8**, score 0.502, **+2 ± 14**. `promotion_gate --stage eval` FAIL. No SPRT. ([wdl colors](../experiments/20260814_wdl_colors/report.md))
- Leaf+result WDL: 180 finished games × 3 roots × 25k → 4 613 450 unique leaves; 20k uniform static labels, all with result. `nnue_wdl_leaves.bin`: best epoch 11, C++ MAE **12.9** (N=1831), clone gate PASS, affine 1.04. Equal-node 25k N=200 seed 20260814: **11-172-17**, score 0.485, **−10 ± 18** (candidate 0.515). `promotion_gate --stage eval` FAIL. No SPRT. ([wdl leaves](../experiments/20260814_wdl_leaves/report.md))
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
- PATH `stockfish` is Stockfish **17**. Official SF18 and dev-20260810-5062aee5 pinned in [`frozen-targets`](../experiments/frozen-targets/manifest.json). Historical “SF18” ladder rungs used SF17.
- Holdout affine fit (N=20157, SF 25k labels): SF 768 is already on SF units (origin 1.05×); frozen baseline is ~2× those labels (origin 0.51×). ([evalscale](../experiments/20260814_evalscale_nodes/report.md))
- Equal-node 25k N=200: `EvalScale=511` on baseline **12-179-9**, +5 ± 16 (coin flip). `nnue_sf25k` @1091 **23-169-8**, +26 ± 19; @1519 **28-160-12**, +28 ± 22. No SPRT. `EvalScale` stays 1000.

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
