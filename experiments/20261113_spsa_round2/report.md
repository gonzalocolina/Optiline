# Second SPSA round on the HL net

`tools/spsa_nodes.py` ran again from the values of [20261113_spsa_hl_sprt](../20261113_spsa_hl_sprt/report.md): 48 constants, fixed 32 000 nodes per move, HL net `nsceper1_hl_full` with `UseExtras` off, UHO book, eleven workers, two game pairs per perturbation, 12 000 planned pairs. It was stopped after 7054 pairs. Six step sizes were changed from `tools/configs/spsa_nodes_steps.json` because the first round had moved those constants far: `SeeQuietPerDepth` 1.5, `FutilityBase` 10, `LmrHistDiv` 700, `QsFutility` 20, `NmpEvalBase` 25, `LmrKiller` 160.

Eleven constants moved at least half a step. The shipped values move them four times as far; the other constants keep their values.

| Constant | Before | SPSA | Steps moved | Shipped |
| --- | ---: | ---: | ---: | ---: |
| `LmrCutoffCount` | 1738 | 1511.3 | -1.42 | 831 |
| `LmrTtCapture` | 1603 | 1424.1 | -1.12 | 887 |
| `AspDeltaBase` | 29 | 27.0 | -1.01 | 21 |
| `LmrNotImproving` | 524 | 646.2 | +0.95 | 1013 |
| `LmrDeeperBase` | 38 | 43.2 | +0.65 | 59 |
| `SeeNoisyPerDepth` | 91 | 84.8 | -0.62 | 66 |
| `HistBonusSub` | 93 | 102.0 | +0.60 | 129 |
| `SeMinDepth` | 11 | 10.7 | -0.58 | 10 |
| `FutilityNoBest` | 60 | 53.1 | -0.57 | 33 |
| `LmrShallower` | 10 | 7.8 | -0.55 | 1 |
| `SeDoubleMargin` | 19 | 16.9 | -0.53 | 10 |

## Line search

Candidate against the values before this round, fixed 50 000 nodes per move, HL net, UHO book. Stopped before the SPRT decided.

| Displacement | Games | Elo |
| ---: | ---: | ---: |
| 2× | 1600 | +5.9 ± 9.9 |
| 4× | 1600 | +9.1 ± 9.9 |
| 7× | 1400 | +0.7 ± 11.0 |

## Confirmation

4× was picked from those games, so it was tested again with a new seed. Same conditions, SPRT [0, 5]:

```text
Results of tune2 vs hbase2 (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 11.66 +/- 6.29, nElo: 19.49 +/- 10.50
LOS: 99.99 %, DrawRatio: 65.56 %, PairsRatio: 1.30
Games: 4204, Wins: 1881, Losses: 1740, Draws: 583, Points: 2172.5 (51.68 %)
Ptnml(0-2): [108, 207, 1378, 254, 155], WL/DD Ratio: 21.59
LLR: 2.95 (100.1%) (-2.94, 2.94) [0.00, 5.00]
```

On the 768×128 net `nnue_search_leaves40k_rw0` with extras on, same node count: +8.8 ± 6.8 Elo over 2996 games, stopped at LLR 1.70.

Speed is unchanged: the 40-position bench at depth 13 runs at 402 000 nodes per second with the old values and 404 000 with the new ones.

No 100 ms match was run. A training job was using the GPU and one CPU core while this round was tested, which a fixed node count does not feel and a time control does.

## Stalled games

Seven confirmation games ended with "connection stalls": fastchess got no `readyok` within 60 s. Six were the old values, one the new, and each counts as a loss for the side that stalled. Removing them leaves the result within 0.4 Elo.

Stalls also happened before any tuning (two in the 03:00–05:00 screens, on the untuned binaries) and in all the tuning screens, on both sides. 20 of the 28 came between 12:20 and 14:30, when three matches ran at once next to the training job. A 3550-game self-play run of one binary at eight games at a time, with full engine I/O traced, had none. The cause is not found. It looks tied to machine load, not to these values.
