# Equal-node with RFP/razor/futility off (N=400)

Date: 2026-08-14. Diagnostic: same nets as `nnue_sf25k` vs baseline, but
`UseRFP=UseRazoring=UseFutility=false` on **both** sides. Isolates eval quality
from those three prunes. N=40 (3-36-1, +17 ± 37) was exploratory.

- A: `baseline_noprune.uci` (internal + extras, those prunes off)
- B: `nnue_sf25k_noprune.uci` (768 extras off, those prunes off)
- `go nodes 25000`, N=400, seed 20260814, max plies 60
- W-D-L from baseline: **44-332-24** (score **0.525**, **+17 ± 14**)
- Candidate score **0.475**

Same sign as the pruning-on N=400 (+21 ± 13). The SF 768 loss is not “margins
fighting a better eval.” Canonical write-up:
[nodes400](../20260814_sf25k_768_nodes400/report.md).
