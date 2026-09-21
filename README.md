# OPTILINE - MOTOR DE AJEDREZ NSCE

Optiline es el repositorio de NSCE, un programa que juega al ajedrez. En cada
turno examina las continuaciones posibles y elige la que considera mejor.

Para decidir, construye un **árbol de búsqueda**: a partir de la posición
actual genera las jugadas legales, después las respuestas a esas jugadas, y
así sucesivamente. Recorrer ese árbol entero es imposible, así que usa **poda
alfa-beta**. Cuando una línea ya no puede mejorar lo que ha encontrado, la
abandona y sigue con otra. Profundiza donde importa y no pierde el tiempo en
variantes que no van a salir.

En esas posiciones no aplica una receta de puntos hecha a mano. Una **red
neuronal** mira el tablero y estima quién está mejor y por cuánto. La red
juzga la posición; el árbol elige el movimiento.

El proyecto quiere ver hasta dónde llega este planteamiento frente a
Stockfish, con la misma máquina y el mismo tiempo por jugada. En el estado
actual, en partidas a 100 ms, NSCE gana unos 145 Elo a Stockfish 18 limitado
a 2200. No es un motor de élite; se puede jugar contra él igual.

## Jugar

Hay un tablero en el navegador. Desde la carpeta del proyecto:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
./play.sh
```

Hace falta un compilador de C++ y CMake. El último comando arranca el motor y
deja el tablero en
[http://127.0.0.1:8765/](http://127.0.0.1:8765/). Se abre esa dirección, se
mueve una pieza y el programa responde.

En la terminal: `./play.sh --cli`. Si ya se usa un programa de ajedrez (Arena,
Cute Chess y similares), basta con apuntarlo a `build/nsce`.

## Licencia

NSCE se distribuye bajo la [GNU GPL versión 3](LICENSE).
