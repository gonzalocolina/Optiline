# Both-color WDL mix — still an equal-node coin flip

Date: 2026-08-14. Follow-up to [wdl games](../20260814_wdl_games/report.md).
Candidate is `768×128` from `--init internal` on static labels of 256
self-play paths (128 openings × both colors), `--target-mode wdl
--result-weight 0.20 --residualize-extras --augment mirror`
(`nets/nnue_wdl_colors.bin`, extras on). One UCI change: `EvalFile`.

## Data

256 games, 100 ms, `--max-plies 200 --both-colors`, `openings_balanced.epd`.
Resumed from 83 after the hidden run was cut. 40m49s of new play.

| Termination | Games | PGN |
| --- | ---: | --- |
| checkmate | 155 | 88 × 1-0, 67 × 0-1 |
| draw (rule) | 25 | 1/2-1/2 |
| max_plies (no result) | 76 | omitted |

Mean 146 plies. **37 620** path positions; **22 344** with a real result.
Color pairing removed the 14–27 mate split of the 64-game run.

## Train

35 907 unique FENs, 128 groups, holdout 3694. Adam 32 ep, lr `4e-4`, seed
20260814. Best epoch 8 (later epochs walked off the WDL target). Net ≠ clone.

## C++ integers vs static teacher

Holdout N=3283, extras on, runtime composite delta 0.

| Engine | MAE vs static labels | Sign |
| --- | ---: | ---: |
| internal + extras | **0.00** | 1.00 |
| `nnue_wdl_colors.bin` + extras | **8.06** | 0.98 |

Clone gate **PASS** (ceiling 15). Affine vs baseline slope 1.00. Closer to the
arbiter than the 64-game net (MAE 27.5). MAE is not promotion.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both, one UCI change.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs wdl_colors | **9-183-8** | **0.502** | **+2 ± 14** | 393302 | 391763 |

0 overruns. `promotion_gate.py --stage eval`: **FAIL**. `baseline.uci`
unchanged. No SPRT.

## Decision

Four times the games and both colors still do not beat this tree. The net
stayed a near-clone (C++ MAE 8) and played like one. Next is not more of the
same path FENs, not KAT, and not search: labels where the tree asks (leaves)
that carry a finished-game result.
