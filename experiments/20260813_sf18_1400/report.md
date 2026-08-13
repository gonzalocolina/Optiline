# NSCE 0.9 vs Stockfish 18 (UCI_Elo 1400)

- NSCE: `build/nsce` v0.9, baseline.uci, 1 thread, Hash 16
- Opponent: Stockfish 18 AVX2, `UCI_LimitStrength=true`, `UCI_Elo=1400`
- Games: 20 (10 opening pairs, colors reversed)
- Movetime: 100 ms
- Max plies: 120
- Openings: `tools/openings_balanced.epd`
- Seed: 20260813
- Date: 2026-08-13

| Match | W-D-L (NSCE) | Score | Elo ±95% |
| --- | ---: | ---: | ---: |
| NSCE 0.9 vs SF18 Elo 1400 | 11-6-3 | 0.700 | +147 ± 146 |

Equal-compute self-play vs NSCE 0.8 at 100 ms / 60 plies was 2-36-2 (indecisive: almost all `max_plies` draws). The Stockfish-limited rung is the current Elo ladder step.
