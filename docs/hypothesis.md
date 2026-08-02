# Hipótesis y protocolo de evaluación

## Hipótesis principal

Una política neuronal puede distribuir el presupuesto de cómputo (ordenación de movimientos, profundidad, reducciones) de forma más eficiente que un conjunto fijo de heurísticas, permitiendo mayor fuerza ajedrecística que Stockfish con la misma CPU, el mismo número de hilos y el mismo tiempo por movimiento.

Batir Stockfish latest a equal-compute es el **norte científico**, no el KPI semanal.

## Métrica primaria (largo plazo)

\[
\Delta Elo = Elo_{NSCE} - Elo_{Stockfish}
\]

bajo \(T_{NSCE} \approx T_{Stockfish}\) y mismos hilos/CPU/memoria.

## KPIs semanales

| KPI | Descripción |
| --- | --- |
| ΔElo (peldaño actual) | Elo vs oponente de la escalera en la que se compite |
| nodes/move | Nodos medios por jugada a TC fijo |
| time overrun | Fracción de jugadas que exceden el presupuesto |
| Elo/nodo (proxy) | ΔElo relativo / nodos (o score de match / nodos) |
| Elo/tiempo | Fuerza a equal-time vs baseline congelado |

## Escalera Elo

1. **Self-play depth ladder** — NSCE depth N vs NSCE depth N-2 (smoke de protocolo).
2. **Motor débil** — p. ej. motor UCI random / muy limitado.
3. **Stockfish reducido** — `UCI_LimitStrength` / `UCI_Elo`, o 1 hilo + hash pequeño + TC corto.
4. **Stockfish equal-time** — mismos hilos, mismo TC, mismo hash razonable; GPU fuera del match.

Subir de peldaño solo cuando el SPRT o el intervalo de Elo indiquen superioridad clara en el peldaño actual.

## Condiciones de match

- Misma máquina, afinidad de CPU fijada si es posible.
- Mismos hilos para ambos motores en el match oficial.
- Mismo control de tiempo (`movetime` o `tc`).
- Openings fijos (PGN/EPD de apertura); ambos colores.
- Cute Chess CLI (preferido) o el runner en `tools/smoke_match.py`.
- Reportar: W/D/L, Elo±error, nodos medios, tiempo medio, ilegalidades/timeouts (deben ser 0).

### Ejemplo cutechess-cli

```bash
cutechess-cli \
  -engine cmd=./build/nsce name=NSCE \
  -engine cmd=stockfish name=SF proto=uci \
    option.UCI_LimitStrength=true option.UCI_Elo=1400 \
  -each proto=uci tc=10+0.1 \
  -gamesover 2 \
  -rounds 50 \
  -resign movecount=3 score=800 \
  -draw movenumber=40 movecount=8 score=20 \
  -openings file=tools/openings.epd format=epd order=random \
  -pgnout games.pgn
```

Ajustar rutas y Elo de SF al peldaño actual. Ver `tools/cutechess_ladder.sh`.

## Ablations (fases futuras)

Activar/desactivar un solo componente por experimento:

- Política de ordenación neuronal vs historial/MVV-LVA
- `Δd` aprendido vs LMR fijo
- Incertidumbre / complejidad vs presupuesto uniforme

Registrar siempre nodos y tiempo además del resultado.

## Telemetría (preparación para aprendizaje)

Cuando se active el log de búsqueda, cada evento debería incluir al menos:

- hash de posición, depth, move index, reduce?, score, cutoff?, best move

Esto alimentará la Etapa 3 (aprendizaje de decisiones de búsqueda) sin acoplar aún la red al hot path.
