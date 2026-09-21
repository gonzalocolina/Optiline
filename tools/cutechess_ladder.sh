#!/usr/bin/env bash
# Ladder helper for cutechess-cli. Requires cutechess-cli. Prefer the pinned
# Stockfish 19 binary; never rely on PATH `stockfish` (this lab's PATH is SF17).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NSCE="${NSCE:-$ROOT/build/nsce}"
if [[ -z "${STOCKFISH:-}" ]]; then
  if [[ -x "$ROOT/third_party/stockfish/stockfish-19" ]]; then
    STOCKFISH="$ROOT/third_party/stockfish/stockfish-19"
  elif [[ -x "$ROOT/third_party/stockfish/stockfish-18" ]]; then
    STOCKFISH="$ROOT/third_party/stockfish/stockfish-18"
  else
    STOCKFISH="stockfish"
  fi
fi
OPENINGS="${OPENINGS:-$ROOT/tools/openings.epd}"
ROUNDS="${ROUNDS:-20}"
TC="${TC:-10+0.1}"
SF_ELO="${SF_ELO:-1400}"

if [[ ! -x "$NSCE" ]]; then
  echo "NSCE binary not found: $NSCE" >&2
  exit 1
fi

if ! command -v cutechess-cli >/dev/null 2>&1; then
  echo "cutechess-cli not found; use tools/smoke_match.py for local smoke." >&2
  exit 1
fi

cutechess-cli \
  -engine cmd="$NSCE" name=NSCE \
  -engine cmd="$STOCKFISH" name="SF_${SF_ELO}" proto=uci \
    option.UCI_LimitStrength=true "option.UCI_Elo=${SF_ELO}" \
  -each proto=uci tc="$TC" \
  -rounds "$ROUNDS" \
  -recover \
  -resign movecount=3 score=800 \
  -draw movenumber=40 movecount=8 score=20 \
  -openings file="$OPENINGS" format=epd order=random \
  -pgnout "${ROOT}/games_ladder.pgn"
