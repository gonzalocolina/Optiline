# Cómo se fabrica y se juzga el evaluador

El orden importa: cada paso existe porque el anterior, si está roto, hace inútiles los siguientes.
No se cambia el árbol de golpe ni se recarga la red. El árbitro tiene que ser reconocible para este PVS.

**Elo (desde 2026-09-15):** `python3 tools/fastchess_match.py` (partidas
completas, adjudicación, pentanomial). `ablation_match.py` / `sprt.py` a
`--max-plies 60` cuentan el corte como tablas (~90 % de las puertas a
igualdad de nodos) y no sirven como veredicto de fuerza.

**Datos:** ≥100 M de self-play a nodos fijos (`nsce_datagen` + bullet
dual-perspective). No escalar `--label static`. Ver [handoff.md](handoff.md).

Protocolo: [knowledge.md](knowledge.md), [experiments.md](experiments.md), [measurement.md](measurement.md).

## 1. Enseñar a copiar al árbitro que el árbol ya entiende

Etiqueta posiciones con la **evaluación estática** del motor congelado (red interna + extras, tal como corre en C++), entrena la misma red `768×128`, y exige que el binario cuantizado reproduzca esas notas.

Por qué: las destilaciones de 200k no probaron la arquitectura; una aprendió la nota completa del profesor y luego el runtime volvió a sumar extras. Si el tubo entrenar → exportar → eval no puede clonar al árbitro actual, cualquier red “mejor” puede ser un artefacto. Esto es la puerta de **exportación**, no el camino de Elo.

```bash
bash train/run_clone_arbiter.sh
# luego igualdad de nodos N≥200 (telemetría) y:
python3 tools/promotion_gate.py --stage clone \
  --validation nets/nnue_clone.validation.json \
  --equal-node experiments/<run>/ablation_summary.json \
  --manifest experiments/<run>/manifest.json
```

`--label static` usa `eval details`, no `go nodes`. `--residualize-extras` porque el 768 suma extras en runtime. El clon que pasa es `--init internal --epochs 0` (MAE C++ 0, igualdad de nodos 8-184-8). El color-flip no es simetría de esta ReLU (`--augment none` o `mirror`); con `full` Adam se alejaba 34 cp en la época 1. La época 0 cuenta como mejor.

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

El entrenador NumPy de arriba es el de la 768 promovida. El siguiente entrenador de Elo es bullet (paso 3), con la misma moneda: `SCALE=400`, λ sobre score/WDL.

## 3. Self-play a nodos fijos ≥ 100 M, dual-perspective, bullet, NSCEPER1

El Elo está en el **volumen y la arquitectura de los datos**, no en más hojas estáticas del profesor. `nsce_datagen` escribe partidas a nodos fijos en bulletformat ChessBoard (perspectiva del bando que mueve, resultado de la partida, puntuación de búsqueda). Un entrenador bullet CUDA aprende una red **dual-perspective** `(768→512)×2` SCReLU. El runtime C++ (`NSCEPER1`) debe reproducir esos enteros antes de cualquier partida.

```bash
# ~12–14 h, ~100–120 M posiciones. 14 hilos. No uses selfplay.py / collect_leaves.py.
./build/nsce_datagen --out train/data/gen0.bin --games 1200000 --nodes 5000 \
  --threads 14 --eval-file nets/nnue_search_leaves40k_rw0.bin --seed 1

# third_party/bullet: example nsce, HIDDEN_SIZE=512, .dual_perspective(),
# inputs::Chess768, SCReLU, QA=255 QB=64 SCALE=400, 8 output buckets.
bash train/run_bullet.sh   # shuffle + CUDA train + pack + 10k float-ref
```

Inferencia (`NSCEPER1`): dos acumuladores int16 (blanco / negro). Feature
`perspective_piece * 64 + oriented_sq` (768, sin cubo de rey). Salida =
Σ SCReLU(acc_stm)·w_stm + Σ SCReLU(acc_nstm)·w_nstm por cubo
`(popcount(occ)-2)/4`. El runtime carga el magic `NSCEPER1`
(`engine/src/nnue.cpp`); empaquetar con `python3 tools/pack_nsceper1.py`.
Cuantiza como documenta bullet. Export check:

```bash
python3 tools/per1_float_ref.py --net nets/nsceper1.bin --n 10000
```

Python cuantizado == C++. Máximo |float − C++| ≤ 2 cp en 10k FEN (dos divisiones
hacia cero), **antes** del primer `fastchess_match.py`.
`UseExtras` va a false en esa comparación (solo la red).

`train/selfplay.py`, `train/collect_leaves.py` y `train/distill.py --label static`
son **legado**. Construyeron el mix 40k promovido. Escalar `--label static`
(80k…640k hojas) no ganó al árbitro que clonaba. No es el siguiente trabajo.

## 4. Juzgar con el evaluador desplegado, no con el MAE en flotante

Misma red, mismos extras sí/no que en partida, enteros como en C++, y luego partidas. El MAE solo sirve para tirar redes rotas, no para promocionar.

```bash
python3 train/validate_nnue.py --engine build/nsce \
  --network nets/nnue_clone.bin --use-extras --gate clone
```

Ya hubo MAE mejor y Elo peor, dos veces. Para `NSCEPER1`: la puerta de
exportación es Python cuantizado == C++ y |float − C++| ≤ 2 cp en 10k FEN,
no el MAE de entrenamiento.

## 5. Lo que ya se midió con el tubo Python (no repetir)

Partidas propias con desenlace y hojas `--label static` (64 y 256 caminos;
20k hojas con WDL copiado; 80k…640k hojas honestas más el camino) siguieron
siendo moneda al aire en el instrumento de 60 plies. El mix de búsqueda 40k
a `go nodes 8000` con **`result-weight 0`** es el que está en
`baseline.uci`. No subir `result-weight`. No recoger más JSONL de hojas.

El `UCI_Elo` 2200 limitado (N=200, **67-88-45**, **+38 ± 36**) es un hándicap,
no un rating. Stockfish 18 sin límite: **0-1-99** a 100 ms, partidas completas.

## 6. Un solo cambio por candidato, y el mismo contrato de extras

- 768 con extras **on**, o red de rey / dual-perspective con extras **off** (medir `UseExtras=false` después de que la red gane; no asumir que se pueden apagar).
- Nunca extras encima de KAT.
- Nunca red nueva + política + controlador + otra escala en el mismo SPRT.

`tools/eval_contract.py` y `tools/promotion_gate.py` rechazan mezclas.

## 7. La puerta de verdad: partidas completas contra este árbol

Pantalla `--st 100 --rounds 300`. Promoción `--tc 8+0.08 --sprt 0 5` (nElo,
modelo por defecto). Un cambio UCI. Elo solo de este arnés.

Igualdad de nodos (`ablation_match.py`) sigue siendo telemetría: dice si el
árbitro ayuda a elegir. Igualdad de tiempo con corte a 60 plies **no** es Elo.

```bash
python3 tools/fastchess_match.py --cfg-b tools/configs/candidate.uci \
  --st 100 --rounds 300 --outdir experiments/$(date +%Y%m%d)_eval_screen
python3 tools/fastchess_match.py --cfg-b tools/configs/candidate.uci \
  --tc 8+0.08 --sprt 0 5 --rounds 3000 --outdir experiments/$(date +%Y%m%d)_eval_sprt
python3 tools/promotion_gate.py --stage eval \
  --sprt experiments/<sprt>/match_baseline_vs_candidate.json \
  --manifest experiments/<sprt>/manifest.json
```

Tras H1, promocionar `EvalFile`. Luego gen1: regenerar con `nsce_datagen` y
la red nueva, reentrenar, repetir (~3 generaciones).

## 8. Solo entonces un evaluador un poco más rico

King buckets / hidden 1024 / amenazas **después** de que gen1 dual-perspective
gane el SPRT. KAT sobre 1 M de raíces Lichess no es evidencia contra entradas
relativas al rey. KAT sobre el mix 40k perdió igualdad de nodos **111-87-2**.
No añadir amenazas ni hidden 256 sobre ese perdedor.

```bash
.venv/bin/python train/train_kat.py --no-threats \
  --data train/data/nsce_search_mix_40k.jsonl \
  --target-mode wdl --search-wdl-scale 400 --teacher-wdl-scale 400 \
  --result-weight 0.0 --epochs 32 --seed 20260814
```

## 9. Retocar la búsqueda solo para el árbitro que ya gane

Cuando una red gane en partidas completas, ahí sí: SPSA agrupado
(`NSCE_TUNE` + weather-factory) y **una** feature de búsqueda por SPRT
[0, 5] a 8+0.08. Política y controlador de LMR, encima de esa eval ganadora.

`--stage search` en `promotion_gate.py` es el único sitio donde EvalScale y flags de poda cuentan como un cambio. Ajustarlas para salvar una red perdedora es hacer trampas al árbol.

## Lo que no entra

Escalar `--label static`. Recargar NumPy. Más features de peón/amenaza o más
anchos **antes** de gen1. Clonar búsqueda GPL o cargar pesos `.nnue` de
Stockfish. Velocidad de inferencia de redes que ya pierden. Una red de
atención que emita el movimiento. Eso no hace que este árbol reconozca al
árbitro; cambia de deporte o recarga un evaluador que ya perdió.
