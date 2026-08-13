# Discarded 2-game SPRT

First controller SPRT stopped after one opening pair (WDL 1-1-0, LLR 3597) because pair-level variance collapsed. That H1 is invalid. `tools/sprt.py` now floors variance at 0.04 and requires `--min-games 40` before accepting H0/H1. Re-run: `experiments/20260813_controller_sprt`.
