# Controller hypothesis log

Date: 2026-08-02

## Setup

- A: [tools/configs/baseline.uci](../../tools/configs/baseline.uci) (`UseSearchController=false`)
- B: [tools/configs/controller.uci](../../tools/configs/controller.uci) (`UseSearchController=true`)
- Equal movetime 60–80 ms, Threads=1, Hash=16, same NNUE/policy off for B except controller on
- Tool: `python3 tools/sprt.py --cfg-b tools/configs/controller.uci`

## Result (updated 2026-08-02, N=80)

- SPRT (80 games, 40 ms, elo0=-5, elo1=+5): **inconclusive**
  - Controller WDL **9-64-7** (score 0.5125, LLR≈0.06)
  - No H1 acceptance; draw-heavy short TC
- Stockfish 17 installed locally; ladder vs SF UCI_Elo=1400 (N=50): NSCE score **0.480 (−14 ± 96 Elo)**

See [experiments/20260802_sprt100/report.md](./20260802_sprt100/report.md).

## Follow-ups

1. Re-run SPRT with N≥100 and eval adjudication (enabled in `ablation_match.play_game`)
2. Fit controller from deep-search telemetry (`TelemetryFile`) where cutoffs after reduced search were verified by full-depth re-search
3. Keep reductions conservative (already clamped to [-1,+2]) until Elo/nodo improves at equal-time
