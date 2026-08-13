# KAT vs internal: nps and equal-node

Date: 2026-08-13. Candidate is the 1M×8-epoch `NSCEKAT1` that lost the equal-time
SPRT (39-112-85, H0). This run separates **eval quality** from **time tax**.

## Fixed depth (UCI `bench 10` / `go depth 10`)

Startpos depth 10: internal 46k nodes / 27 ms / ~1.71M nps; KAT 149k nodes /
82 ms / ~1.82M nps. Throughput is similar; KAT’s tree is ~3× larger.

Three-position `go depth 10` sample:

| Net | Nodes | Time | nps |
| --- | ---: | ---: | ---: |
| internal | 6.25M | 4060 ms | 1.54M |
| KAT | 0.59M | 439 ms | 1.34M |

Kiwipete dominates the internal node count. Across positions, KAT is about
**13% slower per node**, not the 50% gap from the earlier 120k smoke.

## Equal node (`go nodes 25000`, 20 games)

- Openings: `openings_balanced.epd`, seed 20260813, max plies 60
- W-D-L from baseline: **4-12-4** (score 0.500, +0 ± 98)
- Nodes/game: baseline 373k, KAT 337k
- Time/game: baseline 639 ms, KAT 662 ms (~4% slower)

At a shared node budget the 8-epoch net is a coin flip. The equal-time SPRT
loss is therefore **tree shape / effective depth**, not a hopeless eval. More
epochs (same hidden 128) should both lower MAE and, if eval noise falls, prune
better at 100 ms.
