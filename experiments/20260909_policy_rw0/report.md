# From-to policy on the promoted 768

Date: 2026-09-09. One policy-group change vs `baseline.uci`: `UsePolicy=true` +
`PolicyFile=nets/policy_rw0.bin`. `EvalFile` stays
`nets/nnue_search_leaves40k_rw0.bin`. Self-play 256 games, 100 ms, both colors,
13×`Threads=1`, current baseline: **65-61-43** + 87 unfinished
(`train/data/selfplay_policy_rw0.jsonl`). `NSCEPOLY` from-to counts from those
moves. Do not replay `tools/configs/policy.uci` (`EvalFile=internal`).

## Equal node (`go nodes 25000`)

N=200, seed 20260814. Auto `report.md` prints the default movetime line; the
match was **nodes** (`nodes_per_move=25000`).

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| history vs policy_rw0 | **27-166-7** | **0.550** | **+35 ± 20** | 383174 | 380611 |

Candidate score **0.450**. Interval excludes 0 (baseline stronger). 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote. `UsePolicy`
stays false.

## Decision

Piece→to + from→to is too weak to beat history on this eval, same as the
internal-era prior. Do not condition a destination head on a KAT accumulator
(KAT already lost). `baseline.uci` unchanged. SF18 Elo 2200 remains 30-25-25,
+22 ± 64 (not ≥2200).
