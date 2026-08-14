# Cómo se fabrica y se juzga el evaluador

El orden importa: cada paso existe porque el anterior, si está roto, hace inútiles los siguientes.
No se cambia el árbol de golpe ni se recarga la red. El árbitro tiene que ser reconocible para este PVS.

Protocolo de laboratorio: [knowledge.md](knowledge.md), [experiments.md](experiments.md), [measurement.md](measurement.md).

## 1. Enseñar a copiar al árbitro que el árbol ya entiende

Etiqueta posiciones con la **evaluación estática** del motor congelado (red interna + extras, tal como corre en C++), entrena la misma red `768×128`, y exige que el binario cuantizado reproduzca esas notas y no pierda a igualdad de nodos.

Por qué: las destilaciones de 200k no probaron la arquitectura; una aprendió la nota completa del profesor y luego el runtime volvió a sumar extras. Si el tubo entrenar → exportar → eval no puede clonar al árbitro actual, cualquier red “mejor” puede ser un artefacto.

```bash
bash train/run_clone_arbiter.sh
# luego igualdad de nodos N≥200 y:
python3 tools/promotion_gate.py --stage clone \
  --validation nets/nnue_clone.validation.json \
  --equal-node experiments/<run>/ablation_summary.json \
  --manifest experiments/<run>/manifest.json
```

`--label static` usa `eval details`, no `go nodes`. `--residualize-extras` porque el 768 suma extras en runtime.

## 2. Definir una sola moneda, la de NSCE, no la de Stockfish

Convierte las notas del profesor (NSCE o Stockfish) a probabilidad de victoria **con una curva de ese profesor**, y de ahí a la escala de búsqueda de NSCE (`NSCE_SEARCH_WDL_SCALE`, donde viven las podas). Guarda los centipawns crudos como `raw_teacher_cp`.

Si en runtime se suman extras, la red aprende objetivo − extras (`--residualize-extras`). Si es red de rey sin extras, el objetivo entero.

Un centipawn de Stockfish no es un centipawn de NSCE. Entrenar con cifras de otro motor y meterlas en umbrales de este árbol es el fallo de la 768 de Stockfish: mejor examen, peor compañera. La escala afín ya se midió y no lo arregló.

```bash
.venv/bin/python train/train_nnue.py \
  --data train/data/labels.jsonl \
  --target-mode wdl \
  --teacher-wdl-scale <curva_del_profesor> \
  --search-wdl-scale 400 \
  --residualize-extras
```

## 3. Entrenar donde el árbol pregunta, no solo en la raíz

Las etiquetas tienen que parecerse a las hojas reales: quietas de la quiescencia, tácticas, jaques, finales — no las primeras 200k FEN de Lichess puntuadas en la raíz.

```bash
python3 train/collect_leaves.py --engine build/nsce --nodes 25000 --limit 64
python3 train/distill.py --label static --fens train/data/leaves.jsonl \
  --leaf-sites q_stand_pat,static,in_check_static \
  --teacher build/nsce -o train/data/nsce_static_leaves.jsonl
```

## 4. Juzgar con el evaluador desplegado, no con el MAE en flotante

Misma red, mismos extras sí/no que en partida, enteros como en C++, y luego partidas. El MAE solo sirve para tirar redes rotas, no para promocionar.

```bash
python3 train/validate_nnue.py --engine build/nsce \
  --network nets/nnue_clone.bin --use-extras --gate clone
```

Ya hubo MAE mejor y Elo peor, dos veces.

## 5. Datos con resultado, no paseos ni el primer trozo del dump

Partidas propias desde aperturas equilibradas, con el desenlace, mezcla de fases y de posiciones difíciles. Objetivo en espacio de victoria, con una parte de la nota del profesor y una parte del resultado.

```bash
python3 train/selfplay.py --games 64 --movetime 100 \
  --config tools/configs/baseline.uci \
  --positions-out train/data/selfplay_positions.jsonl
python3 train/distill.py --label static --fens train/data/selfplay_positions.jsonl \
  --teacher build/nsce -o train/data/nsce_static_games.jsonl
.venv/bin/python train/train_nnue.py \
  --data train/data/nsce_static_games.jsonl \
  --target-mode wdl --result-weight 0.20 --residualize-extras --init internal
```

200k de “las primeras FEN, go nodes 25000” no produjeron una compañera de búsqueda.

## 6. Un solo cambio por candidato, y el mismo contrato de extras

- 768 con extras **on**, o red de rey con extras **off**.
- Nunca extras encima de KAT.
- Nunca red nueva + política + controlador + otra escala en el mismo SPRT.

`tools/eval_contract.py` y `tools/promotion_gate.py` rechazan mezclas.

## 7. La puerta de verdad: ganar a este árbol, con N grande

Igualdad de nodos, N≥200 (o SPRT), contra el baseline congelado. Si gana, entonces igualdad de tiempo. Hace falta el candidato por encima de 0.5 de forma clara, no un MAE bonito.

A 40 partidas el empate técnico se disfrazó de moneda al aire y a 400 era derrota. Igualdad de nodos dice si el árbitro ayuda a elegir; igualdad de tiempo dice si es demasiado caro.

```bash
python3 tools/ablation_match.py --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/candidate.uci --games 200 --nodes 25000 \
  --outdir experiments/$(date +%Y%m%d)_eval_nodes
python3 tools/sprt.py --cfg-a tools/configs/baseline.uci \
  --cfg-b tools/configs/candidate.uci --max-games 400 --movetime 100 \
  --outdir experiments/$(date +%Y%m%d)_eval_sprt
python3 tools/promotion_gate.py --stage eval \
  --equal-node experiments/<nodes>/ablation_summary.json \
  --sprt experiments/<sprt>/sprt_candidate.json \
  --manifest experiments/<sprt>/manifest.json
```

## 8. Solo entonces un evaluador un poco más rico, todavía simple

Misma tubería ya demostrada: red respecto al rey **sin** el residuo de 12 amenazas, contra la 768 corregida, mismos datos y misma pérdida. Amenazas, pares de peones, hidden 256, política y hardware van después de que esa base gane el SPRT.

```bash
.venv/bin/python train/train_kat.py --no-threats \
  --data train/data/nsce_static_games.jsonl \
  --target-mode wdl --search-wdl-scale 400
```

KAT ya era “más barroco” y perdió. El árbol reconocerá un primo del árbitro actual, no un extraño con más sensores.

## 9. Retocar la búsqueda solo para el árbitro que ya gane

Cuando una red gane nodos y tiempo, ahí sí: un ajuste agrupado de escala/márgenes (RFP, futilidad, razoring, NMP, ProbCut…) para **esa** red. Política y controlador de LMR, encima de esa eval ganadora.

`--stage search` en `promotion_gate.py` es el único sitio donde EvalScale y flags de poda cuentan como un cambio. Ajustarlas para salvar una red perdedora es hacer trampas al árbol.

## Lo que no entra

Más features de peón/amenaza, más anchos, más Stockfish, más velocidad de inferencia de redes que ya pierden, ni una red de atención que emita el movimiento. Eso no hace que este árbol reconozca al árbitro; cambia de deporte o recarga un evaluador que ya perdió.
