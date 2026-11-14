# Rating and promotion of nsceper1_simple1024_test80 — 2026-11-14

Engine: `build/nsce` built from this branch rebased on master `d83ad27`, so it
includes the SPSA-tuned search. Net: `nets/nsceper1_simple1024_test80.bin`
(sha256 `10879697…`), config `tools/configs/nsceper1_simple1024.uci`: the
baseline config with the new EvalFile and `UseExtras false`. The rung runs name
the identical copy under `train/candidates/`, which git ignores. Opponent:
pinned `third_party/stockfish/stockfish-18` (sha256 `6b087694…`), Hash 16,
Threads 1. The host was idle and every match ran at concurrency 10 on 12
threads. All matches are fastchess full games with balanced openings, colours
reversed per pair, and resign adjudication only when both engines report
≥ 1000 cp (`twosided=true`). `run.sh` reproduces all of it.

## Limited-strength Stockfish ladder (100 ms/move, 200 games per rung)

| NSCE | vs | W-D-L | Elo | Pentanomial |
| --- | --- | --- | --- | --- |
| previous baseline (768×128, `baseline_768.uci`) | SF18 `UCI_Elo=2200` | 152-3-45 | **+207.5 ± 54.0** | [3, 1, 38, 2, 56] |
| simple1024_test80 | SF18 `UCI_Elo=2600` | 192-4-4 | **+603.9 ± 155.7** | [0, 0, 4, 4, 92] |
| simple1024_test80 | SF18 `UCI_Elo=2900` | 109-51-40 | **+125.0 ± 42.9** | [5, 7, 30, 30, 28] |
| simple1024_test80 | SF18 `UCI_Elo=3190` (the maximum) | 52-73-75 | **−40.1 ± 37.3** | [14, 26, 33, 23, 4] |
| simple1024_test80 | SF18 unlimited (100 games) | 1-25-74 | **−322.7 ± 64.4** | [26, 21, 3, 0, 0] |

On Stockfish's own `UCI_Elo` scale at 100 ms, the new net plays at about
3025 (from the 2900 rung) to 3150 (from the 3190 rung). The promoted baseline
plays at about 2400. Against unlimited Stockfish 18 the old line scored 0-1-99
([20260915](../20260915_sf18_unlimited_100ms/report.md)); the new net scores
1-25-74. `UCI_Elo` is calibrated at longer time controls and is not
a CCRL rating, so read these as positions on one ladder, not as absolute
ratings.

The baseline's +207 against the 2200 rung replaces the README's +38 ± 36
([20260909](../20260909_sf18_2200_rw0_n200/report.md)) as the like-for-like
reference. That older run used the legacy runner, which cut games at 120 plies
and scored the unfinished ones as draws.

## Promotion SPRT, 8+0.08, [0, 5] nElo

| A vs B | Openings | W-D-L (A) | Elo A−B | LLR | Decision |
| --- | --- | --- | --- | --- | --- |
| simple1024 vs baseline | balanced | 293-1-0 | +5957 ± 40 | +2.96 | **H1: A stronger**, 294 games |
| baseline vs simple1024 (`../20261114_simple1024_promotion_sprt`) | UHO | 123-6-311 | −158.6 ± 27.5 | −2.97 | **H0: A not stronger**, 440 games |

fastchess tests whether engine A is stronger than B. The first run is
therefore the promotion test. The second follows the README example's
orientation (baseline as A) and confirms the result from the other side. UHO
openings give one side the advantage by design, which is why 123 of its 220
pairs ended 1–1.

The first run won almost every game by adjudication, so its 12 adjudications
were checked by Stockfish 18 unlimited at depth 20. In every one the winner was
ahead by +8.4 pawns or more, or had a forced mate. None was a false win.

## Tooling found on the way

- `tools/fastchess_match.py` could not read fastchess's `LLR: x (p%) (lo, hi)`
  line, nor the `H1 was accepted` line, so every fastchess SPRT JSON lacked its
  decision. Fixed, with `tools/tests/test_fastchess_summary.py`. The two JSONs
  here were re-parsed from their stdout.
- `tools/promotion_gate.py` and `tools/promote_eval.py` take the candidate from
  `cfg_b` and require "H1". fastchess accepts H1 when A is stronger, so with the
  README orientation a stronger candidate gets H0. The gate also requires the
  `stockfish-dev` and `stockfish-17` reference binaries, which this host does
  not have. Because of both issues, the promotion was applied by hand: the
  same two-key edit the tool makes (EvalFile and UseExtras in
  `tools/configs/baseline.uci`). The previous config is kept as
  `tools/configs/baseline_768.uci`, and the contract tests in
  `tools/tests/test_eval_pipeline.py` now read it instead of the live baseline.
