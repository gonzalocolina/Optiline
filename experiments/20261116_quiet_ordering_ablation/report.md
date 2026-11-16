# Quiet ordering ablation — 2026-11-16

`bin/master` = origin/master dfda026; `bin/qo` = search/quiet-ordering 1c2a7e2
(-DNSCE_TUNE=ON). simple1024 net, `tools/configs/baseline.uci`, 50 000 nodes per
move, SPRT [0, 5], 6000 games each, five matches in parallel at concurrency 2.
`killers.uci` keeps only killers/countermove as history bonuses; each other
config adds one piece back on top of it (see run.sh).

| Match | Elo | LLR | Result |
|---|---|---|---|
| killers vs master | −0.5 ± 3.4 | −0.96 | inconclusive |
| + quiet-check bonus vs killers | +2.1 ± 3.3 | +0.76 | inconclusive |
| + bad quiets after losing captures vs killers | −2.2 ± 3.4 | −2.02 | inconclusive |
| + pawn-structure history vs killers | +2.1 ± 3.2 | +0.80 | inconclusive |
| + low-ply history vs killers | +0.9 ± 3.2 | −0.03 | inconclusive |

No piece reached H1, so nothing was merged.
