# fastchess match — 20260916_kpi_frozen

- A: `current` = `build/nsce` + `tools/configs/baseline.uci`
- B: `frozen` = `build/nsce-frozen-20260915` + `tools/configs/baseline.uci`
- Limit: tc 8+0.08; concurrency 14; openings `openings_uho.epd` random seed 20260915
- Games play to a result (resign ±1000cp × 4, draw after move 40 |cp|<10 × 8, max 300 moves)
- Date: 2026-09-16

## Result (A − B)

```text
Indexing opening suite...
Started game 1 of 300 (current vs frozen)
Started game 2 of 300 (frozen vs current)
Started game 8 of 300 (frozen vs current)
Started game 3 of 300 (current vs frozen)
Started game 14 of 300 (frozen vs current)
Failed to set position from opening book, invalid FEN or EPD: rnb2knr/1p1pp1qp/p6b/2p2pp1/4P3/P2B1Q1P/1PPP1PP1/R1B1K1NR w KQ f6;
Failed to set position from opening book, invalid FEN or EPD: 1rb1k1n1/p1pp2p1/np5B/4pp1p/1PPPP2q/2b2P1N/P3K1PP/R1Q2B1R b - -;
Failed to set position from opening book, invalid FEN or EPD: 1rb1k1n1/p1pp2p1/np5B/4pp1p/1PPPP2q/2b2P1N/P3K1PP/R1Q2B1R b - -;
Error while creating match: Failed to set position from opening book, invalid FEN or EPD: 1rb1k1n1/p1pp2p1/np5B/4pp1p/1PPPP2q/2b2P1N/P3K1PP/R1Q2B1R b - -;
Failed to set position from opening book, invalid FEN or EPD: r1bqk2r/1Bp2p1p/p2p3n/3Np1p1/4P2P/6P1/PPQP1b2/1RB1NK1R w kq -;
Error while creating match: Failed to set position from opening book, invalid FEN or EPD: rnb2knr/1p1pp1qp/p6b/2p2pp1/4P3/P2B1Q1P/1PPP1PP1/R1B1K1NR w KQ f6;
Error while creating match: Failed to set position from opening book, invalid FEN or EPD: 1rb1k1n1/p1pp2p1/np5B/4pp1p/1PPPP2q/2b2P1N/P3K1PP/R1Q2B1R b - -;
Error while creating match: Failed to set position from opening book, invalid FEN or EPD: r1bqk2r/1Bp2p1p/p2p3n/3Np1p1/4P2P/6P1/PPQP1b2/1RB1NK1R w kq -;
Failed to set position from opening book, invalid FEN or EPD: 1rbqkb1r/ppn1p2p/2p2p2/2Pp2p1/B3P1n1/2N2N2/PP1P1PPP/R1BQK1R1 w Qk d6;
Error while creating match: Failed to set position from opening book, invalid FEN or EPD: 1rbqkb1r/ppn1p2p/2p2p2/2Pp2p1/B3P1n1/2N2N2/PP1P1PPP/R1BQK1R1 w Qk d6;
Tournament was interrupted. To resume the tournament, run: /home/gonzalo/Escritorio/Codigo/Optiline/third_party/fastchess/fastchess -config file=config.json
Finished match
Total Time: 00:00:01 (hours:minutes:seconds)
```

