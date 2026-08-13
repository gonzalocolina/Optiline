# NSCE 0.9 vs Stockfish 18 (UCI_Elo 1600) — aborted

- Partial: 11 games, NSCE 2-4-5 (score 0.36)
- Aborted on game 12: NSCE returned `bestmove 0000` after Stockfish (White) delivered mate.
  The runner probes `status` on the White engine; Stockfish has no such command, so mate was
  not adjudicated and NSCE was asked to move in a terminal position.
- Do not treat this as a completed rung. Re-run with NSCE as the status oracle.
