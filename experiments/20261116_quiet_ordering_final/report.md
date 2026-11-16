# Quiet ordering, final check — 2026-11-16

`bin/ordering` = search/quiet-ordering c3eb6a8 (dfda026 + killers/countermove
as history bonuses, quiet-check bonus, pawn-structure history), release;
`bin/master` = origin/master dfda026, release. simple1024 net,
`tools/configs/baseline.uci` on both sides, 100 ms/move, concurrency 5 on an
otherwise idle host, SPRT [0, 5].

2590-823-2587, N=6000, Elo **+0.2 ± 3.0**, nElo +0.5 ± 8.8, LLR −0.49 →
**inconclusive** (`sprt_100ms/report.md`).

The two pieces that leaned positive at 50 000 nodes (+2.1 each, see
`../20261116_quiet_ordering_ablation/`) do not show up at 100 ms. The branch
was not merged.
