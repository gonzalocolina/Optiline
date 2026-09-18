# Disjoint 40k@8000 from the 8192 dump — coin flip

Date: 2026-09-09. Candidate is `768×128` from `--init internal` on **40 000**
uniform `search_leaf` FENs plus **40 000** path FENs, both **excluded** from
the promoted 40k mix, labeled `go nodes 8000`, `--target-mode wdl
--result-weight 0 --residualize-extras --augment mirror`
(`nets/nnue_search_leaves40k_8192.bin`, extras on). One UCI change: `EvalFile`.
Does **not** overwrite `nets/nnue_search_leaves40k_rw0.bin`. `baseline.uci`
unchanged.

This is a new draw from the enlarged dump (4096 corpus + 8192 append), not a
doubling of the promoted mix (80k already failed).

## Data

After datagen 8192 ([report](../20260909_datagen8192/report.md)): **+36 817 302**
unique leaves, **648 979** path FENs. Distill `--exclude-fens` skipped the
promoted 40k keys. Teacher: current `baseline.uci`, `go nodes 8000`. Mix:
**80 000** rows (`train/data/nsce_search_mix_40k_8192.jsonl`). WDL only on path.

## Train

Adam 32 ep, lr `4e-4`, seed 20260814. Best epoch **32**. Float val MAE vs
search/WDL **146** cp (sign accuracy 0.74). Deployed C++ MAE vs frozen static
**12.26** (N=6901, `--gate none`). MAE is not a promotion signal.

## Equal node (`go nodes 25000`)

N=200, seed 20260814, extras on both. Trust `nodes_per_move=25000` in JSON;
the auto `report.md` prints “Movetime: 100 ms”.

| Match | W-D-L (baseline) | Score A | Elo A−B ±95% | nodes/game A | nodes/game B |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline vs search40k_8192 | **10-180-10** | **0.500** | **+0 ± 15** | 393927 | 398406 |

Candidate score **0.500**. Interval includes 0. 0 overruns.
`equal_node_clearly_winning`: **FAIL**. No SPRT. Do not promote.

## Decision

Keep `nets/nnue_search_leaves40k_rw0.bin`. Do not take this net to SF18 Elo
2200. Next eval sample should come from the **appended** 8192 leaves, not
another uniform draw over the old dump.
