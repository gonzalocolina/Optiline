# simple1024_test80: final run on four public months — 2026-11-13/14

The shape probes
([20261113_net_shape_probes](../20261113_net_shape_probes/report.md)) chose this
run's settings. Graph: (768→1024)×2 SCReLU → 8 material output buckets, WDL 0,
lr 0.001 with cosine decay to 0.001·0.3⁵, batch 16384, 80 superbatches of
100 M positions. Data: linrock/test80-2024 jan–apr `2tb7p.min-v2.v6`, 7.97 G
positions after the filter, so the run makes about one pass over them.
`manifest.json` has the binpack hashes and every setting.

## Training

It trained for 14 h 04 min on the Radeon 680M (ROCm) at about 158 k pos/s, with
no restart.

| Superbatch | 1 | 2 | 6 | 10 | 20 | 40 | 60 | 80 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mean loss | 0.01256 | 0.01094 | 0.00998 | 0.00976 | 0.00958 | 0.00937 | 0.00926 | **0.00920** |

The 6-superbatch probe on two months ended at 0.01025. The last 20 superbatches
gained only 0.00006, so more of the same data adds little; a larger gain would
need more months or a larger net.

Export: `nets/nsceper1_simple1024_test80.bin`, 1 607 752 bytes, sha256
`1087969741e838f82b6fde8d6729908374d5cecb68203374656a323e387094fd`. On 2000
positions it matches the integer reference exactly (0 mismatches) and stays
within 1.02 cp of the float net.

## Screens (`screen.sh`)

These ran as soon as the net was packed: 100 ms/move, balanced openings,
extras off, concurrency 3, 400 games each.

| Final vs | W-D-L | Elo | Pentanomial |
| --- | --- | --- | --- |
| promoted 768×128 baseline | 390-8-2 | **+726.9 ± 132.9** | [0, 0, 2, 8, 190] |
| HL probe (same shape as PR #18) | 328-53-19 | **+356.6 ± 40.5** | [0, 0, 20, 51, 129] |
| s1024 probe (same net, 600 M positions) | 179-175-46 | **+120.1 ± 23.7** | [0, 20, 61, 85, 34] |

The last row is what 13× more data gives the same shape. No 512-wide net was
trained on the full data, so this run does not show whether width or data
earned the gain.

Ratings against Stockfish and the promotion SPRT are in
[20261114_simple1024_test80_elo](../20261114_simple1024_test80_elo/report.md).
