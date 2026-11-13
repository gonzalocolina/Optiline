# fastchess match — 20261113_threat_history_sprt

- A: `search` = `nsce` built from `75fac8f` + `tools/configs/nsceper1_hl_full.uci`
- B: `master` = `nsce` built from `4ac8a70` (master) + `tools/configs/nsceper1_hl_full.uci`
- Limit: 100 ms/move; concurrency 5; openings `openings_uho.epd` random seed 20261113
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-11-13

## Result (A − B)

```text
Results of search vs master (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 53.33 +/- 14.60, nElo: 81.96 +/- 22.07
LOS: 100.00 %, DrawRatio: 61.55 %, PairsRatio: 2.89
Games: 952, Wins: 487, Losses: 342, Draws: 123, Points: 548.5 (57.62 %)
Ptnml(0-2): [15, 32, 293, 65, 71], WL/DD Ratio: 21.54
LLR: 2.97 (100.9%) (-2.94, 2.94) [0.00, 5.00]
```

**487-123-342**, N=952, Elo A−B **+53.3 ± 14.6**, nElo +82.0 ± 22.1, draw ratio 61.5%, pentanomial [15, 32, 293, 65, 71]

SPRT [0, 5] accepted H1 after 952 games. No game ended on time or by a crash. Of the 954 games that finished, two of them after the SPRT had stopped, 781 were adjudicated wins, 50 were mates and 123 were draws.

## What changed

Both sides are Release builds with `-march=native` and LTO, and both load `nets/nsceper1_hl_full.bin`, the HL graph `(768→512)×2 → 32 → 1`, with `UseExtras` off. A is three commits on top of master:

- `4b1317b` stores the raw static eval on a TT miss, so a node that returns by reverse futility, null move or razoring does not call the network again on its next visit.
- `8eac442` indexes the quiet butterfly history by whether the origin and the target square are attacked, and scores quiet moves by which pieces a cheaper piece attacks.
- `75fac8f` turns eighteen literals in `search.cpp` into `SearchTune` fields with the same values. The tree does not change.

Binary SHA-256: A `a0aa4af9734aa3022d966d5008def000f7727ea3b3de8d5eb333e5e41f34789e`, B `3074d20b81aee1d1579740c611b37d13bb6f55bcea3ce7eda950b49c067339f6`.

## Parts

Forty positions (sixteen hand-picked, twenty-four from the UHO book) searched to depth 13 with the HL net:

| Build | Nodes | Nodes that call the network | Nodes per second |
| --- | ---: | ---: | ---: |
| master | 4 168 195 | 65.9% | 358 426 |
| `4b1317b` | 4 136 926 | 59.1% | not measured on the shipped kernel |
| `75fac8f` | 4 377 902 | not measured | 382 312 |

The threat history was also tested alone at a fixed 50 000 nodes per move, same net, same book, SPRT [0, 5], against `4b1317b`: **+20.95 ± 8.71 Elo** over 2242 games, LLR 2.96, H1. Those fixed-node games ran on test binaries where both sides carry the same 16-bit HL kernel. It returns the same evaluation: the bench searches the same 4 168 195 nodes with it and without it.

The 100 ms result is larger than the fixed-node one. The eval cache makes the binary faster, and it also changes which nodes count as TT hits, which was not measured alone at fixed nodes.

## Tried and left out

Each was tested at a fixed 50 000 nodes per move against the build it was added to, and stopped before the SPRT decided. None is in this branch.

| Change | Games | Elo |
| --- | ---: | ---: |
| Non-pawn correction history split by colour, plus minor and major keys | 1000 | −3.8 ± 12.8 |
| Pawn-structure history in quiet ordering | 800 | −0.9 ± 13.3 |
| One ply shallower per aspiration fail high | 1400 | +2.5 ± 10.8 |
| Internal iterative reduction only at PV and cut nodes | 1000 | −1.0 ± 13.6 |
| SEE test for captures whose history is below the good-capture band | 1400 | +0.7 ± 11.1 |

