# SF 25k-node 768: MAE win, equal-node coin flip (N=40, superseded)

Date: 2026-08-14. **Superseded** by N=400
([nodes400](../20260814_sf25k_768_nodes400/report.md)): baseline 43-338-19,
+21 ± 13, candidate score 0.470. Treat this N=40 row as exploratory only.

- A: `tools/configs/baseline.uci` (internal + extras)
- B: `tools/configs/nnue_sf25k.uci` (768, extras off)
- `go nodes 25000`, N=40, seed 20260814, max plies 60
- W-D-L from baseline: **5-32-3** (score **0.525**, **+17 ± 50**)
- Candidate score **0.475**. CI includes 0.
