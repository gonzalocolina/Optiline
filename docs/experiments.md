# Experimental protocol and frozen baseline

## Baseline (canonical)

| Setting | Value |
| --- | --- |
| Binary | `build/nsce` (Release, NSCE 0.8+) |
| UseNNUE | true |
| UsePolicy | false |
| UseSearchController | false |
| Threads | 1 |
| Hash | 16 |
| Time control | `movetime=100` (ablations) / `tc=10+0.1` (ladder when cutechess available) |

Apply via UCI before every match:

```
setoption name Hash value 16
setoption name Threads value 1
setoption name UseNNUE value true
setoption name UsePolicy value false
setoption name UseSearchController value false
```

Config files: [tools/configs/baseline.uci](../tools/configs/baseline.uci).

## Weekly KPIs

Record under `experiments/YYYYMMDD/report.md`:

- ΔElo (or score) on current ladder rung
- nodes/move
- time overrun rate (must be 0)
- Elo/nodo proxy
- timeouts / illegal moves (must be 0)

## Ablation matrix

Run:

```bash
python3 tools/ablation_match.py --matrix --outdir experiments/$(date +%Y%m%d)
```

Matches:

1. baseline vs HCE (`UseNNUE=false`)
2. baseline vs Policy on
3. baseline vs Controller on
4. baseline vs Policy+Controller (only if 2 or 3 show positive signal)

## Elo ladder

```bash
python3 tools/elo_ladder.py --outdir experiments/$(date +%Y%m%d)
```

Peldaños: depth-ladder self-play → weak NSCE → Stockfish limitado (si `stockfish` en PATH).

## Hardware note

Fill in per machine when publishing results (CPU model, cores used, governor).
