# Keeping the HL net inside the SCReLU window

SCReLU is `clamp(x, 0, 1)²`. Its slope is zero outside `(0, 1)`, so a unit that leaves the interval never gets a task gradient again. The 12-epoch run at learning rate 0.001 finished with 12 of 512 feature units alive and a correlation of 0.16 on positions with `|cp| < 100`.

The evaluated network does not change. Training adds a penalty that is zero inside `(0, 1)` and quadratic outside, with coefficient 0.05, so a dead preactivation is pulled back to the boundary. The step size is the 0.0002 this initialisation was written for.

A probe of 80 steps at the destructive rate 0.001:

| Window coefficient | Feature units alive |
| ---: | ---: |
| 0 | 20 / 512 |
| 0.05 | 512 / 512 |

Six epochs on the same 2 million Lichess records, rate 0.0002, coefficient 0.05. Every epoch reported `ft_live 512/512`. Holdout, 2000 positions, float network, side-to-move centipawns:

| Net | Units alive | All positions | `|cp| < 200` |
| --- | ---: | --- | --- |
| rate 0.001, no penalty, 12 epochs | 12 / 512 | corr 0.64, MAE 121 | corr 0.12, prediction std 132 |
| rate 0.0002, penalty 0.05, 6 epochs | 512 / 512 | corr 0.67, MAE 122 | corr 0.39, prediction std 103 |

Loss was still falling at epoch 6 (0.015 → 0.011). The quiet band is where the extra units show up: correlation there went from 0.12 to 0.39, and the predictions are less loud (std 103 against labels whose std is 57). The labels in `|cp| < 100` only spread by 37 cp; after six epochs the corrected net still spreads by 93, so that band is not finished.
