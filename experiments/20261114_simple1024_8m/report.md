# simple1024_8m: the same net on eight months — 2026-11-14/15

The 4-month run ([20261113_simple1024_test80](../20261113_simple1024_test80/report.md))
gained only 0.00006 of loss over its last 20 superbatches. This run asks
whether more data alone helps: same graph and settings, only the data and the
superbatch count change.

## Data

The `2tb7p.min-v2.v6` variant is published for linrock/test80-2024 jan–jun
only (jul–sep exist only as raw `.tar.zst`). The two missing months come from
linrock/test80-2023, which publishes nov and dec in the same variant.
`tools/fetch_test80.sh` now takes `2023-11-nov` style months for that.

| Month | Entries | Kept by the filter |
| --- | ---: | ---: |
| 2023-11 | 2 724 M | 1 331 M |
| 2023-12 | 3 016 M | 1 473 M |
| 2024-01 | 3 512 M | 1 718 M |
| 2024-02 | 3 159 M | 1 545 M |
| 2024-03 | 4 003 M | 1 958 M |
| 2024-04 | 5 618 M | 2 748 M |
| 2024-05 | 4 034 M | 1 973 M |
| 2024-06 | 3 606 M | 1 764 M |
| **Total** | 29 673 M | **14 510 M** |

`stats.jsonl` has the per-bucket counts; `manifest.json` the hashes. The
loader reads the files oldest first through its 4 GB shuffle buffer.

## Training

(768→1024)×2 SCReLU → 8 material buckets, WDL 0, lr 0.001 cosine to
0.001·0.3⁵, batch 16384, 145 superbatches of 100 M (one pass, as the 4-month
run), started by [run.sh](run.sh). 26 h 28 min on the Radeon 680M, about
152 k pos/s, no restart. An SPSA run used 7 CPU threads for the first 2.5 h
without slowing it.

| Superbatch | 10 | 40 | 80 | 110 | 145 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 months | 0.00973 | 0.00941 | 0.00923 | 0.00916 | **0.00915** |
| 4 months | 0.00976 | 0.00937 | **0.00920** (end) | | |

Different data, so the losses only roughly compare. The last 35 superbatches
moved the loss by 0.00001.

Export: `nets/nsceper1_simple1024_8m.bin` (not committed), sha256
`b0ea07753d406fd105ba6bae77bd02671f86ab52a274118367f88ba6e19eef8d`. On 2000
positions it matches the integer reference exactly and stays within 1.02 cp
of the float net.

## Match

Against the promoted 4-month net, both on the 0.12.0 search (`9cec21b`),
`UseExtras` off, 100 ms per move, UHO book, concurrency 3, SPRT [0, 5] capped
at 6000 games ([report](../20261115_simple1024_8m_vs_4m/sprt_100ms/report.md)):

```text
Results of net8m vs net4m (0.1/move, 1t, 16MB, openings_uho.epd):
Elo: 2.03 +/- 3.29, nElo: 5.41 +/- 8.79
Games: 6000, Wins: 2619, Losses: 2584, Draws: 797, Points: 3017.5 (50.29 %)
Ptnml(0-2): [35, 244, 2426, 241, 54], WL/DD Ratio: 14.55
LLR: 0.73 (24.7%) (-2.94, 2.94) [0.00, 5.00]
```

Inconclusive at the cap: +2.0 ± 3.3 Elo. 1.8× the data buys at most a few
Elo for this shape, so the 4-month net stays promoted. The 1024 simple net
looks capacity-bound rather than data-bound; the extra months are better
spent on a larger input layer (king buckets).
