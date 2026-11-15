# SPSA on the simple1024 net — 2026-11-14/15

The search constants on master were tuned on the HL net
([20261113_spsa_hl_sprt](../20261113_spsa_hl_sprt/report.md),
[20261113_spsa_round2](../20261113_spsa_round2/report.md)). The promoted net
is now `nsceper1_simple1024_test80`, which evaluates differently and searches
about 1.8× more nodes per second, so this round tunes the same constants on it.

## Tuning

`tools/spsa_nodes.py`, started from the 0.12.0 values:

- net `nets/nsceper1_simple1024_test80.bin`, `UseExtras` off (as `tools/configs/baseline.uci`)
- 48 constants, step sizes in `steps.json`: `tools/configs/spsa_nodes_steps.json` with round 2's six changes
- fixed 32 000 nodes per move, UHO book, 7 workers, 2 game pairs per perturbation
- 14 000 pairs (28 000 games), run to the end in about 2.5 h, next to a training job on the GPU

The final values are in `state.json`. Twelve constants moved at least half a
step. The shipped values move those twelve seven times as far (chosen below);
the other 36 keep their values.

| Constant | Before | SPSA | Steps moved | Shipped |
| --- | ---: | ---: | ---: | ---: |
| `FutilityHistDiv` | 3587 | 4098.1 | +1.70 | 7165 |
| `FutilityPerDepth` | 111 | 97.1 | −1.39 | 20 (the spin's minimum) |
| `LmrQuietDivX100` | 165 | 183.1 | +1.20 | 291 |
| `HistBonusMul` | 179 | 194.5 | +1.04 | 288 |
| `LmrNotImproving` | 1013 | 1120.6 | +0.84 | 1767 |
| `SeeOrderDiv` | 60 | 57.3 | −0.68 | 41 |
| `LmrShallower` | 1 | 3.6 | +0.65 | 19 |
| `HistPrune` | 3980 | 4133.2 | +0.61 | 5052 |
| `SeMinDepth` | 10 | 9.7 | −0.56 | 8 |
| `IirDepth` | 4 | 3.7 | −0.55 | 2 (the spin's minimum) |
| `HistBonusCap` | 1586 | 1639.4 | +0.53 | 1960 |
| `SeeQuietPerDepth` | 7 | 7.8 | +0.53 | 13 |

## Line search

Candidate (k× the SPSA move of those twelve) against the 0.12.0 values. Both
sides are Release builds of `9cec21b` that differ only in
`engine/include/nsce/tune.hpp`, with `tools/configs/baseline.uci`. 50 000
nodes per move, UHO book, 800 opening pairs each
([run.sh](../20261115_spsa_simple1024_linesearch/run.sh)).

| Displacement | Games | Elo | Pentanomial |
| ---: | ---: | ---: | --- |
| 2× | 1600 | +7.6 ± 6.9 | [17, 48, 632, 89, 14] |
| 4× | 1600 | +8.9 ± 6.3 | [6, 53, 653, 70, 18] |
| 7× | 1600 | **+14.6 ± 7.0** | [11, 48, 628, 89, 24] |

## Confirmation

7× was picked from those games, so it was tested again with new seeds,
SPRT [0, 5].

Fixed 50 000 nodes, concurrency 9, seed 77115:

```text
Results of x7 vs base (50000 nodes, 1t, 16MB, openings_uho.epd):
Elo: 13.94 +/- 5.71, nElo: 34.76 +/- 14.22
Games: 2294, Wins: 1049, Losses: 957, Draws: 288, Points: 1193.0 (52.01 %)
Ptnml(0-2): [17, 60, 915, 124, 31], WL/DD Ratio: 16.60
LLR: 2.98 (101.1%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

100 ms per move on an otherwise quiet machine (only the 8-month net SPRT ran
beside it, also at concurrency 3), seed 20261117:

```text
Results of x7 vs base (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 6.95 +/- 3.66, nElo: 20.21 +/- 10.64
Games: 4098, Wins: 1805, Losses: 1723, Draws: 570, Points: 2090.0 (51.00 %)
Ptnml(0-2): [19, 122, 1690, 194, 24], WL/DD Ratio: 12.31
LLR: 2.97 (100.8%) (-2.94, 2.94) [0.00, 5.00]
SPRT ([0.00, 5.00]) completed - H1 was accepted
```

The gain at 100 ms is about half the fixed-node one. The 7× values prune
harder (`FutilityPerDepth` and `IirDepth` reach their minimum, `LmrShallower`
goes from 1 to 19), so this round has only been measured at 100 ms and at
50 000 nodes; a longer time control is still untested.

The binary built from the commit that ships these values has the same
SHA-256 as the tested `x7` (`fb85866f…`).

## Stalls

One game in the 100 ms SPRT (x7 stalled) and one in the 4× screen (x4
stalled) ended in "connection stalls", as in earlier rounds. Each counts as a
loss for the candidate.

## Report bug

`tools/fastchess_match.py` reported the fixed-node confirmation as
"inconclusive". fastchess prints the `SPRT ... H1 was accepted` line after the
last separator, and the wrapper only parsed the last results block. The
wrapper now reads that line too (`summarize_output`, with a test), and the
confirmation's `report.md` and `match_x7_vs_base.json` were corrected by hand.
Earlier SPRT reports written by this wrapper may show the same wrong
"inconclusive"; their LLR lines are right.
