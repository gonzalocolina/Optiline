# Lab knowledge

Compiled findings from NSCE experiments. Raw match logs stay under
`experiments/YYYYMMDD_*/`. This file is the **working model**: what is frozen,
what has been measured, what failed, and what to try next.

| Field | Value |
| --- | --- |
| Last updated | 2026-08-27 (80k honest leaf+path WDL: C++ MAE 3.09, equal-node 12-175-13, −2 ± 17) |
| Engine | NSCE 0.10 |
| Frozen baseline | `tools/configs/baseline.uci` — `EvalFile=internal`, `UseExtras=true`, `UseSearchController=false`, `UsePolicy=false`, Hash 16 |
| Protocol | [hypothesis.md](hypothesis.md), [eval_pipeline.md](eval_pipeline.md), [experiments.md](experiments.md), [measurement.md](measurement.md) |

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
- Compete on **Elo/time** and **Elo/node**, not by cloning SFNNv13 or copying GPL search. Labels (cp / WDL) are allowed; Stockfish `.nnue` weights are not. Teacher cp is converted through **that teacher's** WDL curve into the **NSCE search coin** before it touches pruning thresholds. ([eval_pipeline.md](eval_pipeline.md))
- A feature that wins **fixed nodes** and loses **fixed time** is too expensive, not “almost good.” Interpret the two matches separately. ([measurement.md](measurement.md))
- Holdout MAE (float or C++) **rejects wreckage**; it does not promote. The tree reads signs and margins, not mean error. ([eval_pipeline.md](eval_pipeline.md))
- The train → quantize → C++ **export** path can copy the frozen 768: `--init internal --epochs 0` has engine MAE **0** vs static labels and equal-node N=200 is **8-184-8** (score 0.500, +0 ± 14, identical nodes). Color-flip augmentation is not a ReLU symmetry (epoch-0 MAE 290 cp, sign accuracy 0). With `--augment none` or `mirror`, Adam stays on those notes (16 ep last-epoch MAE 0.14 / 0.33). Epoch 0 is now eligible as best. ([clone trainer](../experiments/20260814_clone_trainer/report.md))
- 64 self-play games with real results (WDL mix 0.20, 768 + extras) produce a different net (C++ MAE 27.5 vs static) that is an equal-node **coin flip** (14-172-14, +0 ± 18). 256 games, both colors, stay a near-clone (C++ MAE 8.1) and still a coin flip (9-183-8, +2 ± 14). Search leaves from those finished games (4.6M unique, 20k labeled with a **copied** game result) are also a coin flip (11-172-17, candidate score 0.515, **−10 ± 18** to baseline). After fixing provenance, 80k honest search leaves plus 21 705 path WDL is still a coin flip (12-175-13, **−2 ± 17**, C++ MAE 3.09). Not a companion. ([wdl games](../experiments/20260814_wdl_games/report.md), [wdl colors](../experiments/20260814_wdl_colors/report.md), [wdl leaves](../experiments/20260814_wdl_leaves/report.md), [80k leaves](../experiments/20260827_wdl_leaves80k/report.md))
- `Elo/nodo` is diagnostic only: pruning changes what a node means.

### Frozen baseline (v0.10)

- Eval: HCE-distilled `768×128×1` (`EvalFile=internal`) **plus** classical `extras()` (mobility, files, outposts, hanging, king). `UseExtras=true` is **load-bearing** on this net: turning it off lost SPRT. Keep extras on the 768 path; keep extras off for king-bucket nets.
- King-bucket nets (KAT / HalfKP): **`extras()` off**. The residual fights the net and biases learning.
- Search: PVS, TT, LMR, NMP with verify, RFP, razoring, futility, LMP, ProbCut, IIR, singular extensions (double SE on PV only), continuation 1/2/4/6, pick-next, QS fail-soft, quiet SEE, Lazy SMP. Ablation flags freeze each of these in `baseline.uci`. Hash stays **16 MB**. `EvalScale` stays **1000** until a calibrated scale wins equal-node N≥200 and a SPRT. Iterative-deepening still stops a new iteration when remaining `< last_iter / 2` (stricter soft-stop was a coin flip).
- Policy and search controller: **off** on the frozen baseline.

### Measurement pitfalls (paid for in lab time)

- **N=20** Elo intervals on the SF ladder are too wide to promote. Use **N≥40** (paired colors). Equal-node self-play at 25k nodes is ~1 s/game here: **N=40 is still too wide** (±50 Elo, ~80% draws). Use **N≥200** (or SPRT) for that gate.
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
| Mix clone leaves into that train set and trust the holdout | Val is clone-dominated; best epoch 0 ships the clone | [wdl games](../experiments/20260814_wdl_games/report.md) |
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

**Not played:** unrestricted equal-compute Stockfish 18 (no `UCI_LimitStrength`) against the frozen `stockfish-18` hash. Historical rungs used PATH Stockfish 17.

Self-play: NSCE 0.9 vs 0.8 at 100 ms / 60 plies was 2-36-2 (almost all `max_plies` draws) — indecisive.

---

## Next levers

The 2026-08-13 evening speedups (**KAT madd inference** + **latched time-up / less clock overhead**) roughly **double nodes in 200–700 ms searches**. Converting that 2× into Elo via the same KAT net, extras-off, Hash 32, or a stricter ID stop **failed or was a coin flip**. Affine `EvalScale` did not rescue the SF 768 either. Do not skip to a later item to “try something.”

The evaluator is now manufactured and judged in a **fixed order** ([eval_pipeline.md](eval_pipeline.md)). Later steps are illegal until the earlier gate passes.

1. **Clone pipe passed, including the trainer.** Export MAE 0, equal-node 8-184-8. Color-flip was why Adam walked off; `--augment none|mirror` stays (16 ep MAE 0.14 / 0.33). Epoch 0 is kept when later epochs are worse. ([clone trainer](../experiments/20260814_clone_trainer/report.md))
2. **One currency: NSCE search scale.** Teacher cp → that teacher's WDL → NSCE search cp. Keep raw cp as metadata. Never train on Stockfish cp and prune with NSCE thresholds.
3. **Label leaves, not the first 200k root FENs.** Already used for the clone (`collect_leaves.py` + `--sample-uniform`). Keep that for any new labels.
4. **Judge the deployed integers**, then games. MAE is a reject filter. Clone gate is live (`validate_nnue.py --gate clone`).
5. **80k honest leaf+path WDL is still a coin flip** (C++ MAE 3.09, equal-node 12-175-13, −2 ± 17). Do not raise `result-weight`. Not KAT. Next corpus work is streaming self-play toward more unique leaves; unfinished games stay unlabeled. ([80k leaves](../experiments/20260827_wdl_leaves80k/report.md))
6. **One change, extras contract.** 768 extras on, or king-bucket extras off. Never extras on KAT. Never net + policy + controller + scale in one SPRT.
7. **True gate: beat this tree, N large.** Equal-node N≥200 (or SPRT) clearly above 0.5 vs frozen baseline; then equal-time. A net that wins nodes and loses clock is expensive.
8. **Only then** a king-relative net **without** the 12-threat residual, same data/loss, vs the corrected 768.
9. **Only then** grouped search-margin/EvalScale retune, then policy / LMR controller, for the eval that already won.

Closed and not next: SF-teacher 768 (`nnue_sf25k.bin` at 1000/1091/1519), NSCE self-distill 200k, replay `kat_candidate.bin` / `kat_nsce25k.bin` / `nnue_nsce25k_ft.bin` at 100 ms, extras-off on the frozen 768, Hash 32 at 100 ms, another ID/TM constant at 100 ms (fail-low extra budget unmeasured), more ProbCut/IIR/SE constants, hidden 256 at 1M, another N=20 ladder, controller clamp relax, policy on KAT before an eval H1, 5M Lichess, 500k more labels for this KAT or this SF 768. `kHidden≠128` still waits on a 768×128 that wins equal-node. SF Elo 2000, N≥40 only after a **promoted** eval, and only against the frozen SF18 binary. Richer pawn/threat features, wider nets, faster inference of nets that already lose, and move-emitting attention nets stay out: they change the sport or reload a loser.

---

## Findings log

### 2026-08-27

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
