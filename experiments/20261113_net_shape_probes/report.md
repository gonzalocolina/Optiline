# Net shape probes on public binpacks — 2026-11-13

Question: before the long run on the four `linrock/test80-2024` months, which
NSCEPER1 shape and settings should it use? All probes saw the same data and the
same position count, so they differ only in shape and target.

## Engine change first: the HL net was slow, not weak

The HL net from PR #18 spent most of its time in the 1024 → 32 layer. Each of
the 32 neurons multiplied int32 lanes and widened to int64. The new kernels
(`engine/src/nnue.cpp`) square in 16 bits instead: `madd(x·w, x)` with
x = clamp(acc, 0, 255). The trick is exact whenever every |w| ≤ 127, and bullet
clips weights to ±1.98, which is ±127 after ×64. The loader checks the bound,
and a net outside it takes the old wide path.

| Net | Eval before | Eval after | Search nps before → after |
| --- | --- | --- | --- |
| HL (768→512)×2 → 32 → 1 | 3.5 µs | 1.06 µs | 308 k → 679 k (same nodes and scores) |
| simple (768→1024)×2 → 8 buckets | — | 46–68 ns | — |

The same change lets simple nets take any width that is a multiple of 16, up to
1024 (`kPer1Acc`). It also adds 8 material output buckets, (pieces − 2) / 4,
which is the bucket rule the MLP net already uses. Tests:
`Per1SquareKernelMatchesTheWideFormula` covers widths 512/768/1024, both paths
and every graph. `Per1SquareKernelSurvivesSaturatedInputs`,
`Per1SimpleOutputBucketFollowsPieceCount`, `Per1WideAccumulatorStaysIncremental`
and `Per1RejectsWidthsTheKernelsCannotStep` cover the rest.

## Data

Probes trained on jan+feb (`run.sh`, `run_wdl.sh`): 6 superbatches of 100 M
positions each, so 600 M positions, about 18 % of those two months. The filter
(`train/bullet_binpack_stats.rs`) keeps a position when its ply is ≥ 16, it is
not in check, |score| ≤ 10000 and the move is quiet.

| Month | Entries | Kept | Mean |score| kept |
| --- | --- | --- | --- |
| jan | 3.51 G | 1.72 G | 287 |
| feb | 3.16 G | 1.55 G | 284 |
| mar | 4.00 G | 1.96 G | 284 |
| apr | 5.62 G | 2.75 G | 285 |
| total | 16.29 G | 7.97 G | |

Kept positions per output bucket range from 8.6 % (bucket 7) to 15.2 %
(bucket 3). No bucket is starved.

## Probes

| Run | Graph | lr / batch | Final loss (mean of superbatch 6) | Train time | File |
| --- | --- | --- | --- | --- | --- |
| probe_s512 | (768→512)×2 → 8 buckets | 0.001 cos / 16384 | 0.01073 | 30 min | 0.80 MB |
| probe_hl | (768→512)×2 → 32 → 1 | 0.0002 cos / 8192 (PR #18 settings) | 0.01111 | 33 min | 0.85 MB |
| probe_s1024 | (768→1024)×2 → 8 buckets | 0.001 cos / 16384 | **0.01025** | 63 min | 1.61 MB |
| probe_s1024_wdl30 | same, 30 % game result | 0.001 cos / 16384 | (other target) | 80 min* | 1.61 MB |

\* It shared the host with the match screens.

The packed nets match the integer reference bit for bit: 0 mismatches in 2000
positions each. The float-vs-quantised gap is ≤ 1.02 cp for the simple nets.
For probe_hl it reaches 10.9 cp in the worst position, over the 8 cp gate. That
is quantisation error in the 32-wide hidden layer, not an engine bug.

Search speed, one position, 3 M nodes, loaded host: s512 741 k nps, s1024
588 k, HL 327 k, the 768×128 baseline 755 k.

## Games

All games use build/nsce from this branch with extras off, 1 thread, 16 MB hash
and concurrency 3. Another session's SPSA was running at the same time with
11 workers; both sides of every game shared that load.

| A vs B | Limit | Openings | N | Elo A−B | Pentanomial |
| --- | --- | --- | --- | --- | --- |
| s1024 vs base768 (`tools/configs/baseline.uci`) | 100 ms | UHO | 200 | **+188.5 ± 44.4** | [0, 0, 48, 5, 47] |
| s1024 vs HL | 100 ms | UHO | 200 | **+128.9 ± 35.6** | [0, 2, 54, 15, 29] |
| s1024 vs s512 | 100 ms | UHO | 200 | −8.7 ± 20.7 | [4, 7, 81, 6, 2] |
| s1024 vs s512 | 25 k nodes | balanced | 300 | **+44.2 ± 31.4** | [10, 25, 55, 37, 23] |
| s1024 vs s512 | 100 ms | balanced | 300 | +7.0 ± 25.9 | [8, 29, 71, 33, 9] |
| s1024 WDL 0.3 vs WDL 0 | 100 ms | balanced | 300 | **−41.9 ± 29.0** | [18, 41, 56, 29, 6] |

UHO openings split 81 % of the s1024/s512 pairs 1–1, so the close comparisons
were run again on balanced openings.

## Decision

- **Bucketed simple over HL.** On equal data it reaches a lower loss and is
  about 1.8× faster. It wins by ~130 Elo, which puts HL at about +60 over the baseline.
  The HL hyperparameters are PR #18's; a higher HL lr was not tried.
- **Width 1024 over 512.** At equal nodes the eval is better by +44 ± 31. At
  100 ms on this loaded host the 21 % nps cost leaves +7 ± 26. The final run
  sees 13× more positions than the probes, and wide nets gain the most from
  more data. Longer time controls favour eval quality.
- **WDL 0.** Mixing in 30 % game result costs 42 ± 29 Elo on this data.
- **Kept:** lr 0.001 with cosine decay to 0.001·0.3⁵, batch 16384 and the
  filter above.

Final run: `NSCE_GRAPH=simple NSCE_FT=1024 NSCE_SUPERBATCHES=80 NSCE_WDL=0`,
all four months (8.0 G positions, about one pass). Its results are in
[20261113_simple1024_test80](../20261113_simple1024_test80/).

## Reproduce

```bash
bash tools/fetch_test80.sh
bash experiments/20261113_net_shape_probes/run.sh       # s512, hl, s1024
bash experiments/20261113_net_shape_probes/run_wdl.sh   # s1024 WDL 0.3
bash experiments/20261113_net_shape_probes/screen.sh    # UHO screens
bash experiments/20261113_net_shape_probes/screen2.sh   # balanced screens
```

The nets are not in git. Their sha256:

- `nets/nsceper1_probe_s512.bin` dd745f61a049c0944a2ec4b0ff55229614909d3715658890a476958a02dc61dd
- `nets/nsceper1_probe_hl.bin` da4cbc4045ce15585aa3cfb899e74620e08d0ebc41b40614dcb7b357be4aa164
- `nets/nsceper1_probe_s1024.bin` ed3114c7813066bbaaa3a838fccf164930416f58e1c324a6635b62b72600a18e
- `nets/nsceper1_probe_s1024_wdl30.bin` c013d04d73da7fb75b31b5862410924db32cd89becbdefc9680c34a39b855882
