# Full HL training inside the SCReLU window

Same graph, `(768→512)×2` SCReLU → 32 SCReLU → 1, on the 2 million Lichess positions. Step size 0.0002. Window penalty 0.05, which is zero inside `(0, 1)` and pulls a preactivation back from outside. The engine still evaluates plain SCReLU.

The run resumed the six-epoch weights that already had 512/512 feature units alive, then continued. Every epoch kept `ft_live 512/512`. Training loss fell from 0.0108 to 0.0094. The held-out correlation on positions with `|cp| < 200` peaked at **0.455** on the third resumed epoch and did not improve again for six epochs, so the run stopped. The saved net is that peak, not the last epoch: later epochs fit the training loss and gave back the quiet band.

`nets/nsceper1_hl_full.bin`, 853228 bytes, SHA-256 `2934f8872ad19f7001c43b59339bdca9f293b267ba66db09922c34f7f0998c47`.

## Holdout, engine, extras off

1998 positions. Two FENs were rejected as illegal.

| Band | MAE (cp) | Correlation | Prediction std | Label std |
| --- | ---: | ---: | ---: | ---: |
| All | 119.9 | 0.668 | 188 | 289 |
| `|cp| < 200` | 60.1 | 0.421 | 102 | 55 |
| `|cp| < 100` | 54.5 | 0.239 | 89 | 35 |

The 12-epoch net trained at learning rate 0.001, with 12 of 512 units alive, had correlation 0.12 on `|cp| < 200` and a prediction std of 132.

## Games

100 ms, 200 games, UHO, seed 20261018. Baseline **137-12-51**, **+159.8 ± 43.4** Elo. Draw ratio 46%. The killed-unit net on the same screen was +311.8 ± 62.6 with a 23% draw ratio. [Screen](../20261018_hl_full_screen/report.md).
