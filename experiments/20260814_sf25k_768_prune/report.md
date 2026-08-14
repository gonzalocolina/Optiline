# Prune / tree-shape diagnostic (depth 10)

Suite: 6 `nsce_bench` FENs. Binary must be built with `NSCE_STATS=ON`.

- Baseline `baseline`: 5703868 nodes, 4275 ms, 1334238 nps
- Candidate `nnue_sf25k`: 2708083 nodes, 1476 ms, 1834744 nps
- Node ratio (candidate / baseline): **0.47×**
- nps ratio: 1.38×

H1 of pruning: candidate nodes ≤ ~1.2× baseline (not the KAT startpos ~3×) and any nps drop smaller than the node reduction.
**Tree gate: PASS (narrower or similar).**

| Side | nodes | nps | null cut/att | razor | rfp | futility | lmp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 5703868 | 1334238 | 23852/46736 (51%) | 5889/12748 (46%) | 209186/209186 (100%) | 1152289 | 1367938 |
| nnue_sf25k | 2708083 | 1834744 | 12753/30094 (42%) | 1593/3194 (50%) | 121505/121505 (100%) | 601483 | 876102 |

## Per position

| Position | baseline nodes | candidate nodes | ratio |
| --- | ---: | ---: | ---: |
| startpos | 46236 | 101526 | 2.20× |
| kiwipete | 3822436 | 520559 | 0.14× |
| endgame | 172756 | 205900 | 1.19× |
| pos4 | 943659 | 1318684 | 1.40× |
| pos5 | 519337 | 398481 | 0.77× |
| pos6 | 199444 | 162933 | 0.82× |

Kiwipete is 67% of baseline nodes; the 0.47× total is not a uniform narrower
tree. Startpos is 2.20× bushier. Equal-node N=400 still lost
([nodes400](../20260814_sf25k_768_nodes400/report.md)). No SPRT.
