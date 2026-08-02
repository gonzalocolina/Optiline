# Controller hypothesis log

Date: 2026-08-02

## Setup

- A: [tools/configs/baseline.uci](../../tools/configs/baseline.uci) (`UseSearchController=false`)
- B: [tools/configs/controller.uci](../../tools/configs/controller.uci) (`UseSearchController=true`)
- Equal movetime 60–80 ms, Threads=1, Hash=16, same NNUE/policy off for B except controller on
- Tool: `python3 tools/sprt.py --cfg-b tools/configs/controller.uci`

## Result

- SPRT (12 games, ply-cap): **inconclusive** (all draws)
- Ablation with eval adjudication (N=6, 50 ms): baseline vs controller **1-5-0**, Elo A−B **+58 ± 282**
  - No evidence controller helps; baseline not clearly worse either (CI includes 0)
- Conclusion to date: **hypothesis unsupported at current N/TC**; keep controller opt-in and conservative

## Follow-ups

1. Re-run SPRT with N≥100 and eval adjudication (enabled in `ablation_match.play_game`)
2. Fit controller from deep-search telemetry (`TelemetryFile`) where cutoffs after reduced search were verified by full-depth re-search
3. Keep reductions conservative (already clamped to [-1,+2]) until Elo/nodo improves at equal-time
