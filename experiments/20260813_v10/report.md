# NSCE 0.10 vs Stockfish 18 (limited strength)

- NSCE: `build/nsce` v0.10, baseline.uci, 1 thread, Hash 16
- Opponent: Stockfish 18 AVX2 (`UCI_LimitStrength=true`)
- Games: 20 per rung (10 opening pairs, colors reversed)
- Movetime: 100 ms
- Max plies: 120
- Openings: `tools/openings_balanced.epd`
- Seed: 20260813
- Status oracle: NSCE `status` (Stockfish has no such command)
- Date: 2026-08-13

| Match | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| vs SF18 Elo 1400 | 19-0-1 | 0.950 | +512 ± 1888 |
| vs SF18 Elo 1600 | 15-2-3 | 0.800 | +241 ± 234 |
| vs SF18 Elo 1800 | 8-9-3 | 0.625 | +89 ± 118 |
| vs SF18 Elo 2000 | 7-8-5 | 0.550 | +35 ± 120 |

v0.9 on the same 1400 protocol was 11-6-3 (score 0.700, +147). The 1600 rung had previously aborted on `bestmove 0000`.

The ±95% intervals are wide at N=20; treat scores as exploratory. Overruns: 0. Several 1800/2000 games hit `max_plies` draws.

Current ladder step: Stockfish 18 `UCI_Elo=1800`–`2000`. Equal-compute unrestricted Stockfish remains the long-term target; the main remaining gap is evaluation (tiny 768×128 net vs SFNNv10/v13).
