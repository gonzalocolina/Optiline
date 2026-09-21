# NSCE

NSCE (Neural Search Chess Engine) es un motor de ajedrez UCI escrito en C++20.
Juega a través del protocolo estándar, de modo que puede usarse desde cualquier
interfaz compatible (Arena, Cute Chess, este repositorio o un cliente propio).

El proyecto investiga si una política neuronal puede asignar el presupuesto de
búsqueda —ordenación de movimientos, profundidad y reducciones— con más
aprovechamiento que un conjunto fijo de heurísticas. El criterio de éxito no es
ganar a Stockfish limitado por `UCI_Elo`, sino acercarse a Stockfish 19 con la
misma CPU, los mismos hilos y el mismo control de tiempo.

Este repositorio se llama Optiline; el binario y el identificador UCI son
`NSCE`.

## Estado

La versión actual es la 0.10. El generador de movimientos legales está
comprobado con perft. La búsqueda es PVS con las podas y extensiones habituales
de un motor contemporáneo, evaluación NNUE `768×128×1` más un residual
clásico, y un pool de hilos persistente entre comandos `go`.

Frente a la red interna del propio motor, la red promovida gana unos
145 ± 45 Elo en partidas completas a 100 ms. Frente a Stockfish 18 sin límite
de fuerza, en las mismas condiciones, el resultado fue 0–1–99: el motor sigue
muy por detrás del norte que se ha fijado. Esa distancia es el objeto de
trabajo, no un resultado que se pretenda disimular.

## Arquitectura

| Componente | Papel |
| --- | --- |
| Tablero y movegen | Representación bitboard, jaques, clavadas y *en passant* legales |
| Búsqueda | PVS / alfa-beta, tabla de transposición, SEE, Lazy SMP |
| Evaluación | NNUE cuantizada (`EvalFile`) y, en el baseline, residual `extras()` |
| Interfaz | UCI (`Hash`, `Threads`, `EvalFile` y flags de ablación) |
| Datos | `nsce_datagen` escribe posiciones en formato bullet para reentrenar |

El código de búsqueda y los pesos `.nnue` de Stockfish no forman parte de este
árbol. Sí se permiten etiquetas de un motor profesor (centipawns o WDL) para
entrenar redes propias.

La configuración promovida está en `tools/configs/baseline.uci`: hash de 16 MB,
la red `nets/nnue_search_leaves40k_rw0.bin`, extras activados, política y
controlador de búsqueda desactivados.

## Compilación

Hace falta un compilador C++20 (GCC o Clang), CMake 3.16 o posterior y, para
las pruebas, Python 3 con NumPy.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
ctest --test-dir build --output-on-failure
```

En Release, CMake activa por defecto `-march=native`, LTO y AVX2. Pueden
desactivarse con `-DNSCE_NATIVE=OFF`, `-DNSCE_LTO=OFF` y `-DNSCE_AVX2=OFF`.
Las sanitizers (`NSCE_SANITIZE`, `NSCE_TSAN`) y la telemetría de búsqueda
(`NSCE_STATS`) están pensadas para desarrollo, no para partidas de Elo.

## Uso

```bash
./build/nsce
```

El proceso habla UCI por la entrada estándar. Para una partida local contra el
baseline, con tablero en el navegador:

```bash
./play.sh
```

Abre [http://127.0.0.1:8765/](http://127.0.0.1:8765/). La misma sesión en
terminal: `./play.sh --cli`.

Microbenchmark de búsqueda con la red promovida:

```bash
./build/nsce_bench 12 1 1 nets/nnue_search_leaves40k_rw0.bin
```

## Entrenamiento y partidas de medición

El generador de datos vive en el propio motor (`build/nsce_datagen`). El
entrenamiento y el empaquetado de redes se documentan en
[train/README.md](train/README.md). Los conjuntos de posiciones y los
checkpoints no se publican en git; ocupan varios gigabytes y se regeneran.

Las comparaciones de Elo se hacen con partidas completas (adjudicación de
abandono y tablas), no con cortes a un número fijo de plies. El runner está en
`tools/fastchess_match.py` y espera un binario de
[fastchess](https://github.com/Disservin/fastchess) en `third_party/fastchess`.
Los informes resumidos de esos matches están en `experiments/`.

Stockfish se usa como referencia externa. Los binarios no se versionan: hay
que colocar `stockfish-19` (y, si se desea, el pin histórico `stockfish-18`)
en `third_party/stockfish/`, según [third_party/stockfish/README.md](third_party/stockfish/README.md).
El `stockfish` del PATH no es una referencia fiable.

## Estructura del repositorio

```text
engine/        Motor: tablero, búsqueda, evaluación, UCI y datagen
nets/          Pesos NNUE promovidos
tools/         Tablero local, matches, configuraciones UCI y pruebas
train/         Entrenamiento y exportación de redes
experiments/   Informes de partidas y manifiestos de medición
play.sh        Atajo para jugar contra el baseline
```

## Licencia

NSCE se distribuye bajo la [GNU GPL versión 3](LICENSE).
