# fastchess match — 20261113_spsa_hl_sprt

- A: `tuned` = `nsce` built from `171fdfb` + `tools/configs/nsceper1_hl_full.uci`
- B: `master` = `nsce` built from `7cdd3e2` (master) + `tools/configs/nsceper1_hl_full.uci`
- Limit: 100 ms/move; concurrency 5; openings `openings_uho.epd` random seed 20261114
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of tuned vs master (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 51.29 +/- 13.99, nElo: 81.71 +/- 21.96
LOS: 100.00 %, DrawRatio: 64.24 %, PairsRatio: 3.30
Games: 962, Wins: 497, Losses: 356, Draws: 109, Points: 551.5 (57.33 %)
Ptnml(0-2): [16, 24, 309, 67, 65], WL/DD Ratio: 33.33
LLR: 2.94 (100.0%) (-2.94, 2.94) [0.00, 5.00]
```

**497-109-356**, N=962, Elo A−B **+51.3 ± 14.0**, nElo +81.7 ± 22.0, draw ratio 64.2%, pentanomial [16, 24, 309, 67, 65]

SPRT [0, 5] accepted H1 after 962 games. No game ended on time or by a crash. Of the 963 games that finished, one of them after the SPRT had stopped, 813 were adjudicated wins, 40 were mates and 110 were draws.

Both sides are Release builds with `-march=native` and LTO, and both load `nets/nsceper1_hl_full.bin` with `UseExtras` off. The only difference is 41 default values in `engine/include/nsce/tune.hpp`. Binary SHA-256: A `4bdab14a8f4821f7da8b5d2deb75ddbf8085b7a2b05e0f975c2cecb9c8f123d5`, B `a0aa4af9734aa3022d966d5008def000f7727ea3b3de8d5eb333e5e41f34789e`.

## How the values were found

`tools/spsa_nodes.py` ran SPSA over the 48 constants in `tools/configs/spsa_nodes_steps.json` at a fixed 32 000 nodes per move, HL net, UHO book. Eleven workers, two game pairs per perturbation, Fishtest schedule with `r_end` 0.003 and 14 000 planned pairs. The run was stopped after 8484 pairs (16 968 games).

Sixteen constants had moved at least half a step by then:

| Constant | Before | SPSA | Steps moved | Shipped |
| --- | ---: | ---: | ---: | ---: |
| `LmrHistDiv` | 8192 | 9231.8 | +2.08 | 14951 |
| `SeMinDepth` | 6 | 6.8 | +1.54 | 11 |
| `AspDeltaBase` | 14 | 16.4 | +1.19 | 29 |
| `NmpEvalBase` | 160 | 183.6 | +1.18 | 314 |
| `QsFutility` | 200 | 215.1 | +1.01 | 298 |
| `HistMalusMul` | 250 | 264.3 | +0.95 | 343 |
| `SeeOrderDiv` | 36 | 39.7 | +0.93 | 60 |
| `NmpEvalDepthMul` | 20 | 17.0 | -0.76 | 0 |
| `LmrCutoffCount` | 1024 | 1133.9 | +0.69 | 1738 |
| `SeeQuietPerDepth` | 25 | 22.3 | -0.68 | 7 |
| `LmrQuietDivX100` | 230 | 220.0 | -0.67 | 165 |
| `FutilityBase` | 120 | 110.4 | -0.64 | 58 |
| `LmrKiller` | 512 | 592.4 | +0.63 | 1035 |
| `LmrQuietBaseX100` | 80 | 84.5 | +0.56 | 109 |
| `LmrTtCapture` | 1024 | 1113.1 | +0.56 | 1603 |
| `CapFutilityPerDepth` | 200 | 207.6 | +0.51 | 249 |

SPSA had moved them slowly, so the same direction was tried further out. Each row below multiplies the displacement of those sixteen constants and leaves the other 32 at their SPSA value. Every match is the candidate against the values before tuning, fixed 50 000 nodes per move, HL net, UHO book, SPRT [0, 5].

| Displacement | Games | Elo | SPRT |
| ---: | ---: | ---: | --- |
| 1× | 1600 | +15.4 ± 9.8 | stopped at LLR 1.60 |
| 2× | 1688 | +27.2 ± 9.8 | H1 |
| 3× | 1582 | +28.2 ± 10.0 | H1 |
| 4.5× | 1190 | +39.9 ± 12.3 | H1 |
| 6.5× | 884 | +51.9 ± 13.8 | H1 |
| 9× | 1180 | +40.2 ± 12.3 | H1 |

The shipped values are the 6.5× row. The fixed-node games ran on test binaries where both sides carry the same 16-bit HL kernel, which returns the same evaluation as the shipped one.

## Other conditions

The 6.5× values against the values before tuning:

| Net | Nodes per move | Games | Elo | SPRT [0, 5] |
| --- | ---: | ---: | ---: | --- |
| HL `nsceper1_hl_full` | 200 000 | 598 | +41.5 ± 15.3 | stopped at LLR 1.73 |
| 768×128 `nnue_search_leaves40k_rw0`, extras on | 50 000 | 3004 | +12.2 ± 6.9 | stopped at LLR 2.42 |

The 4.5× values on the 768×128 net reached H1 at +14.8 ± 6.8 over 2848 games.

## Limits

The constants were tuned on `nsceper1_hl_full`, which lost to the 768×128 baseline by 150 Elo in [20261018_hl_full_vs_baseline](../20261018_hl_full_vs_baseline/report.md). A stronger HL net may want different values, and the same tool can be run again on it. `SeMinDepth` 11 leaves singular extensions almost unused at these node counts, and the longest search tested was 200 000 nodes per move. The sixteen constants were scaled together, so none of them has been searched alone.

