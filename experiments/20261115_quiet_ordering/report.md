# Quiet move ordering — 2026-11-15

Commit 89e93cb (later rebased onto dfda026 as 1c2a7e2, without root ordering) on
top of master 9cec21b, simple1024 net,
`tools/configs/baseline.uci` on both sides.

Changes: killers/countermove as history bonuses instead of a fixed stage ahead
of all quiets; good/bad quiet split behind losing captures; pawn-structure
history; low-ply history; bonus for safe direct quiet checks; root moves
ordered by nodes. Insertion-sorting the quiets was tried and dropped (no speed
gain, different tie-breaks).

## SPSA (32k nodes, 10 000 pairs, 7 workers)

Nothing moved off the starting guesses: OrderKiller0 20071, OrderKiller1 15956,
OrderCounter 11900, QuietBadThreshold −17764, PawnHistScale 101, LowPlyScale 4,
QuietCheckBonus 12396 (`tuned.uci`).

## SPRT [0, 5] at 100 ms/move, tuned vs master

2588-837-2575, N=6000, Elo **+0.8 ± 3.1**, LLR −0.09 → **inconclusive**
(`sprt_100ms/report.md`). Not merged.

## SPRT [0, 5] at 50 000 nodes, RootNodeOrder 1 vs 0 (both tuned)

2635-710-2655, N=6000, Elo **−1.2 ± 3.2**, LLR −1.41 → **inconclusive**
(`sprt_root_50k/report.md`). Root ordering by nodes was removed from the branch.

The per-piece follow-up is in `../20261116_quiet_ordering_ablation/`.

At fixed depth the first-move cutoff rate rose 84.84 % → 85.14 % and the tree
grew 5–11 %; speed could not be measured cleanly on the loaded host.
