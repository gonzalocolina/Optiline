# Stockfish install + SPRT controller (N=80) — 2026-08-02

## Stockfish

- Binary: `third_party/stockfish/stockfish` (Stockfish 17, ubuntu x86-64 AVX2)
- Symlink: `~/.local/bin/stockfish`
- Tools resolve via `PATH`, `$STOCKFISH`, or `third_party/stockfish/stockfish`

## SPRT: controller vs baseline

| Setting | Value |
| --- | --- |
| A | `tools/configs/baseline.uci` |
| B | `tools/configs/controller.uci` |
| Games | **80** (target ≥50–100) |
| Movetime | 40 ms |
| Max plies | 28 + eval adjudication (±100 cp) |
| H0 / H1 | elo_B−elo_A ≤ −5 / ≥ +5 |
| Bounds | ±2.944 (α=β=0.05) |

**Result:** `inconclusive`

| W (controller) | D | L | Score B | LLR final |
| --- | --- | --- | --- | --- |
| 9 | 64 | 7 | 0.5125 | ≈ +0.06 |

Interpretation: with N=80 at this TC the LLR never hit accept/reject bounds. Point estimate slightly favors the controller (~+9 Elo raw from score) but **CI is huge**; no SPRT acceptance of H1. High draw rate dominates.

Raw: `sprt_controller.json`, `sprt_controller.log`.

## Elo ladder (N=50 / rung)

| Rung | W-D-L | Score | Elo ±95% |
| --- | --- | --- | --- |
| depth d5 vs d3 | 3-47-0 | 0.530 | +21 ± 96 |
| depth d4 vs d1 | 13-37-0 | 0.630 | +92 ± 100 |
| **Stockfish Elo 1400** | **7-34-9** | **0.480** | **−14 ± 96** |

Baseline NSCE is roughly parity with SF@1400 at 40 ms / game (noise ±96). External rung **unlocked**.

## Next

- Raise TC (e.g. 100–200 ms) and N≥200 if seeking SPRT decision on controller
- Or train controller from deep telemetry before another SPRT
- Optionally raise SF UCI_Elo rung once NSCE clearly beats 1400
