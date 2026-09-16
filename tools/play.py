#!/usr/bin/env python3
"""Play a game against NSCE (browser board or ASCII terminal)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from uci_common import UciEngine  # noqa: E402

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
UCI_MOVE = re.compile(r"^[a-h][1-8][a-h][1-8][nbrq]?$")
UNICODE = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


def fen_board(fen: str) -> str:
    """64-character placement, a8..h1, empty squares as '.'."""
    cells: list[str] = []
    for char in fen.split()[0]:
        if char == "/":
            continue
        if char.isdigit():
            cells.extend("." * int(char))
        else:
            cells.append(char)
    if len(cells) != 64:
        raise ValueError(f"bad FEN placement: {fen}")
    return "".join(cells)


def square_index(square: str) -> int:
    return (8 - int(square[1])) * 8 + (ord(square[0]) - 97)


def piece_on(board: str, square: str) -> str:
    return board[square_index(square)]


def _san_key(text: str) -> str:
    value = text.strip().replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    value = value.replace("o-o-o", "O-O-O").replace("o-o", "O-O")
    value = value.replace("O-O-O", "OOO").replace("O-O", "OO")
    for noise in ("+", "#", "!", "?", "x", "=", "-"):
        value = value.replace(noise, "")
    return value.lower()


def uci_to_san(fen: str, uci: str, legal: list[str]) -> str:
    """Algebraic notation for a legal UCI move (check symbols omitted)."""
    board = fen_board(fen)
    frm, to = uci[:2], uci[2:4]
    promo = uci[4] if len(uci) > 4 else ""
    piece = piece_on(board, frm)
    if not piece or piece == ".":
        return uci
    dest_piece = piece_on(board, to)
    is_pawn = piece in "Pp"
    capture = dest_piece != "." or (is_pawn and frm[0] != to[0])
    if piece in "Kk" and abs(ord(frm[0]) - ord(to[0])) == 2:
        return "O-O-O" if to[0] == "c" else "O-O"
    dest = to
    if is_pawn:
        san = f"{frm[0]}x{dest}" if capture else dest
        if promo:
            san += f"={promo.upper()}"
        return san
    letter = piece.upper()
    others = [
        move
        for move in legal
        if move != uci
        and piece_on(board, move[:2]) == piece
        and move[2:4] == to
        and (len(move) > 4) == bool(promo)
        and (not promo or move[4] == promo)
    ]
    extra = ""
    if others:
        files = {move[0] for move in others}
        ranks = {move[1] for move in others}
        if frm[0] not in files:
            extra = frm[0]
        elif frm[1] not in ranks:
            extra = frm[1]
        else:
            extra = frm
    return f"{letter}{extra}{'x' if capture else ''}{dest}"


def resolve_move(text: str, fen: str, legal: list[str]) -> str | None:
    raw = text.strip()
    if not raw or not legal:
        return None
    compact = raw.replace("-", "").replace(" ", "").lower()
    if UCI_MOVE.match(compact):
        if compact in legal:
            return compact
        if len(compact) == 4:
            promos = [move for move in legal if move.startswith(compact)]
            if len(promos) == 1:
                return promos[0]
        return None
    wanted = _san_key(raw)
    hits = [move for move in legal if _san_key(uci_to_san(fen, move, legal)) == wanted]
    if len(hits) == 1:
        return hits[0]
    return None


def ascii_board(fen: str, unicode_pieces: bool = True) -> str:
    board = fen_board(fen)
    side = fen.split()[1] if len(fen.split()) > 1 else "w"
    rows = ["  a b c d e f g h"]
    for rank in range(8, 0, -1):
        cells = []
        for file in range(8):
            piece = board[(8 - rank) * 8 + file]
            if piece == ".":
                cells.append(".")
            elif unicode_pieces:
                cells.append(UNICODE[piece])
            else:
                cells.append(piece)
        rows.append(f"{rank} {' '.join(cells)} {rank}")
    rows.append("  a b c d e f g h")
    rows.append(f"turno: {'blancas' if side == 'w' else 'negras'}")
    return "\n".join(rows)


class Game:
    def __init__(
        self,
        engine: UciEngine,
        human: str = "white",
        movetime_ms: int = 1000,
        nodes: int = 0,
        fen: str = "startpos",
    ) -> None:
        self.engine = engine
        self.human = human
        self.movetime_ms = movetime_ms
        self.nodes = nodes
        self.start_fen = fen
        self.label = "NSCE 2200"
        self.moves: list[str] = []
        self.sans: list[str] = []
        self.last_score_cp = 0
        self.last_depth = 0
        self.last_nps = 0
        self.message = ""
        self.engine.new_game()

    def reset(self, human: str | None = None) -> None:
        if human is not None:
            self.human = human
        self.moves = []
        self.sans = []
        self.last_score_cp = 0
        self.last_depth = 0
        self.last_nps = 0
        self.message = "Nueva partida."
        self.engine.new_game()

    def _fen_key(self) -> str:
        return "startpos" if self.start_fen == "startpos" else self.start_fen

    def fen(self) -> str:
        dumped = self.engine.current_fen(self._fen_key(), self.moves)
        return dumped if dumped else START_FEN

    def legal(self) -> list[str]:
        return self.engine.legal_moves(self._fen_key(), self.moves)

    def status(self) -> str:
        return self.engine.status(self._fen_key(), self.moves)

    def _human_ply(self, index: int) -> bool:
        return (index % 2 == 0) == (self.human == "white")

    def _record(self, uci: str) -> str:
        san = uci_to_san(self.fen(), uci, self.legal())
        self.moves.append(uci)
        self.sans.append(san)
        return san

    def _search(self) -> str:
        stm_white = self.fen().split()[1] == "w"
        if self.nodes > 0:
            uci = self.engine.go_nodes(self._fen_key(), self.moves, self.nodes)
        else:
            uci = self.engine.go_movetime(self._fen_key(), self.moves, self.movetime_ms)
        raw = self.engine.last_score_cp
        self.last_score_cp = raw if stm_white else -raw
        self.last_depth = self.engine.last_depth
        self.last_nps = self.engine.last_nps
        return uci

    def maybe_engine_move(self) -> str | None:
        state = self.status()
        if state != "ongoing":
            self.message = _status_es(state)
            return None
        if self._human_ply(len(self.moves)):
            return None
        uci = self._search()
        if uci in ("0000", "(none)", "none"):
            self.message = _status_es(self.status())
            return None
        san = self._record(uci)
        state = self.status()
        if state != "ongoing":
            self.message = f"NSCE juega {san}. {_status_es(state)}"
        else:
            self.message = f"NSCE juega {san}."
        return uci

    def play_human(self, text: str) -> str:
        if self.status() != "ongoing":
            raise ValueError(_status_es(self.status()))
        if not self._human_ply(len(self.moves)):
            raise ValueError("No es tu turno.")
        uci = resolve_move(text, self.fen(), self.legal())
        if uci is None:
            raise ValueError(f"Jugada ilegal: {text}")
        san = self._record(uci)
        state = self.status()
        if state != "ongoing":
            self.message = f"Juegas {san}. {_status_es(state)}"
        else:
            self.message = f"Juegas {san}."
        return san

    def undo(self) -> None:
        if not self.moves:
            self.message = "No hay jugadas que deshacer."
            return
        if not self._human_ply(len(self.moves) - 1) and len(self.moves) >= 2:
            self.moves.pop()
            self.sans.pop()
        self.moves.pop()
        self.sans.pop()
        self.message = "Deshecho."

    def hint(self) -> str:
        if self.status() != "ongoing":
            raise ValueError(_status_es(self.status()))
        uci = self._search()
        san = uci_to_san(self.fen(), uci, self.legal()) if uci not in ("0000", "(none)", "none") else uci
        self.message = f"Pista: {san} ({uci})"
        return uci

    def snapshot(self) -> dict[str, Any]:
        fen = self.fen()
        status = self.status()
        return {
            "fen": fen,
            "moves": list(self.moves),
            "sans": list(self.sans),
            "legal": self.legal() if status == "ongoing" else [],
            "status": status,
            "side": fen.split()[1] if len(fen.split()) > 1 else "w",
            "human": self.human,
            "last_score_cp": self.last_score_cp,
            "depth": self.last_depth,
            "nps": self.last_nps,
            "movetime_ms": self.movetime_ms,
            "label": self.label,
            "engine_to_move": status == "ongoing" and not self._human_ply(len(self.moves)),
            "message": self.message or _status_es(status),
        }


def _status_es(status: str) -> str:
    return {
        "ongoing": "Tu turno.",
        "checkmate": "Jaque mate.",
        "stalemate": "Ahogado.",
        "draw": "Tablas.",
    }.get(status, status)


def run_cli(game: Game) -> None:
    use_unicode = sys.stdout.isatty()
    print(f"{game.label} — escribe e4, Nf3 o e2e4. Comandos: hint, undo, eval, moves, new, resign, help, quit")
    game.maybe_engine_move()
    while True:
        print()
        print(ascii_board(game.fen(), unicode_pieces=use_unicode))
        status = game.status()
        if game.sans:
            print("jugadas:", " ".join(_pair_sans(game.sans)))
        if game.message:
            print(game.message)
        if status != "ongoing":
            print(_status_es(status))
            cmd = input("new / quit > ").strip().lower()
            if cmd in ("quit", "exit", "q"):
                return
            if cmd in ("new", "n"):
                game.reset()
                game.maybe_engine_move()
            continue
        if not game._human_ply(len(game.moves)):
            game.maybe_engine_move()
            continue
        try:
            raw = input("tu jugada > ").strip()
        except EOFError:
            print()
            return
        if not raw:
            continue
        key = raw.lower()
        if key in ("quit", "exit", "q"):
            return
        if key in ("help", "h", "?"):
            print("Jugadas en SAN (e4, Nf3, O-O) o UCI (e2e4). hint, undo, eval, moves, new, resign, quit")
            continue
        if key in ("new", "n"):
            game.reset()
            game.maybe_engine_move()
            continue
        if key in ("undo", "u"):
            game.undo()
            continue
        if key in ("resign", "r"):
            print("Te rindes.")
            return
        if key == "moves":
            fen = game.fen()
            legal = game.legal()
            print(" ".join(f"{uci_to_san(fen, move, legal)}={move}" for move in legal))
            continue
        if key == "eval":
            print(f"eval estática {game.engine.evaluate(game._fen_key(), game.moves)} cp")
            continue
        if key == "hint":
            try:
                game.hint()
            except ValueError as error:
                print(error)
            continue
        try:
            game.play_human(raw)
        except ValueError as error:
            print(error)
            continue
        if game.status() == "ongoing":
            print("NSCE piensa...")
            game.maybe_engine_move()


def _pair_sans(sans: list[str]) -> list[str]:
    paired: list[str] = []
    for i in range(0, len(sans), 2):
        number = i // 2 + 1
        if i + 1 < len(sans):
            paired.append(f"{number}.{sans[i]} {sans[i + 1]}")
        else:
            paired.append(f"{number}.{sans[i]}")
    return paired


PLAY_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Jugar vs NSCE</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: ui-sans-serif, system-ui, sans-serif;
    background: #14161c; color: #ece7dc; min-height: 100vh;
    display: flex; justify-content: center; padding: 24px;
  }
  main { display: grid; gap: 20px; grid-template-columns: auto 280px; align-items: start; }
  h1 { font-size: 1.15rem; margin: 0 0 12px; font-weight: 600; }
  .board-wrap { display: grid; grid-template-columns: 18px repeat(8, 64px); grid-template-rows: repeat(8, 64px) 18px; }
  .coord { color: #8b8374; font-size: 12px; display: grid; place-items: center; }
  .sq {
    width: 64px; height: 64px; display: grid; place-items: center;
    font-size: 42px; cursor: pointer; user-select: none; position: relative;
  }
  .light { background: #ecd9b0; }
  .dark { background: #b58863; }
  .pc {
    position: relative; z-index: 1; line-height: 1; pointer-events: none;
  }
  .pc.w { color: #fff; }
  .pc.b { color: #111; }
  .selected { outline: 3px solid #f4e27c; outline-offset: -3px; }
  .last::before {
    content: ""; position: absolute; inset: 0;
    background: rgba(214, 196, 72, 0.34); pointer-events: none;
  }
  .dot::after {
    content: ""; width: 16px; height: 16px; border-radius: 50%;
    background: rgba(20,22,28,.35); position: absolute;
  }
  .capture::after {
    content: ""; width: 58px; height: 58px; border-radius: 50%;
    border: 4px solid rgba(20,22,28,.32); position: absolute;
  }
  aside { background: #1d2129; border-radius: 12px; padding: 16px; }
  .msg { min-height: 2.4em; color: #d8c9a3; }
  .moves { height: 220px; overflow: auto; background: #14161c; padding: 8px 10px;
           border-radius: 8px; font-family: ui-monospace, monospace; font-size: 13px; line-height: 1.5; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
  button, select {
    background: #2c3340; color: inherit; border: 0; border-radius: 8px;
    padding: 8px 10px; cursor: pointer; font: inherit;
  }
  button:hover { background: #3a4252; }
  .meta { color: #9a9284; font-size: 13px; }
  @media (max-width: 820px) {
    main { grid-template-columns: 1fr; }
    .board-wrap { grid-template-columns: 18px repeat(8, 12vw); grid-template-rows: repeat(8, 12vw) 18px; }
    .sq { width: 12vw; height: 12vw; font-size: 8vw; }
  }
</style>
</head>
<body>
<main>
  <section>
    <h1 id="title">NSCE 2200</h1>
    <div id="board" class="board-wrap"></div>
  </section>
  <aside>
    <p class="msg" id="msg">Cargando…</p>
    <p class="meta" id="meta"></p>
    <div class="row">
      <label>Color
        <select id="color">
          <option value="white">Blancas</option>
          <option value="black">Negras</option>
        </select>
      </label>
      <label>Tiempo
        <select id="time">
          <option value="200">0.2 s</option>
          <option value="500">0.5 s</option>
          <option value="1000" selected>1 s</option>
          <option value="3000">3 s</option>
        </select>
      </label>
    </div>
    <div class="row">
      <button id="new">Nueva</button>
      <button id="undo">Deshacer</button>
      <button id="hint">Pista</button>
    </div>
    <div class="moves" id="moves"></div>
  </aside>
</main>
<script>
const PIECES = {K:'♚',Q:'♛',R:'♜',B:'♝',N:'♞',P:'♟',k:'♚',q:'♛',r:'♜',b:'♝',n:'♞',p:'♟'};
let state = null, selected = null, thinking = false;

function fenBoard(fen) {
  const out = [];
  for (const ch of fen.split(' ')[0]) {
    if (ch === '/') continue;
    if (/\d/.test(ch)) out.push(...'.'.repeat(+ch));
    else out.push(ch);
  }
  return out;
}
function sqName(file, rank) { return 'abcdefgh'[file] + rank; }
function humanWhite() { return state.human === 'white'; }

function render() {
  const boardEl = document.getElementById('board');
  boardEl.innerHTML = '';
  const pieces = fenBoard(state.fen);
  const last = state.moves.length ? state.moves[state.moves.length - 1] : '';
  const legalFrom = selected
    ? state.legal.filter(m => m.slice(0, 2) === selected)
    : [];
  const ranks = humanWhite() ? [8,7,6,5,4,3,2,1] : [1,2,3,4,5,6,7,8];
  const files = humanWhite() ? [0,1,2,3,4,5,6,7] : [7,6,5,4,3,2,1,0];
  for (const rank of ranks) {
    const lab = document.createElement('div');
    lab.className = 'coord';
    lab.textContent = rank;
    boardEl.appendChild(lab);
    for (const file of files) {
      const sq = sqName(file, rank);
      const idx = (8 - rank) * 8 + file;
      const el = document.createElement('div');
      const light = (file + rank) % 2 === 1;
      el.className = 'sq ' + (light ? 'light' : 'dark');
      if (selected === sq) el.classList.add('selected');
      if (last && (last.slice(0,2) === sq || last.slice(2,4) === sq)) el.classList.add('last');
      const dest = legalFrom.find(m => m.slice(2,4) === sq);
      if (dest) el.classList.add(pieces[idx] === '.' ? 'dot' : 'capture');
      el.dataset.sq = sq;
      if (pieces[idx] && pieces[idx] !== '.') {
        const glyph = document.createElement('span');
        glyph.className = 'pc ' + (pieces[idx] === pieces[idx].toUpperCase() ? 'w' : 'b');
        glyph.textContent = PIECES[pieces[idx]];
        el.appendChild(glyph);
      }
      el.onclick = () => onSquare(sq);
      boardEl.appendChild(el);
    }
  }
  boardEl.appendChild(document.createElement('div'));
  for (const file of files) {
    const lab = document.createElement('div');
    lab.className = 'coord';
    lab.textContent = 'abcdefgh'[file];
    boardEl.appendChild(lab);
  }
  document.getElementById('title').textContent = state.label || 'NSCE 2200';
  let msg = (state && state.message) || '';
  if (thinking) msg = msg ? (msg + ' NSCE piensa…') : 'NSCE piensa…';
  document.getElementById('msg').textContent = msg;
  const evalTxt = state.depth
    ? `eval ${state.last_score_cp > 0 ? '+' : ''}${state.last_score_cp} cp · d${state.depth}`
    : '';
  document.getElementById('meta').textContent = evalTxt;
  document.getElementById('moves').textContent = pairSans(state.sans).join('\n');
  document.getElementById('color').value = state.human;
}

function pairSans(sans) {
  const rows = [];
  for (let i = 0; i < sans.length; i += 2) {
    rows.push(`${i/2+1}. ${sans[i]}${sans[i+1] ? ' ' + sans[i+1] : ''}`);
  }
  return rows;
}

function needsPromo(from, to) {
  const pieces = fenBoard(state.fen);
  const idx = (8 - +from[1]) * 8 + (from.charCodeAt(0) - 97);
  const pawn = pieces[idx] === 'P' || pieces[idx] === 'p';
  return pawn && (to[1] === '8' || to[1] === '1');
}

async function onSquare(sq) {
  if (thinking || state.status !== 'ongoing') return;
  const pieces = fenBoard(state.fen);
  const idx = (8 - +sq[1]) * 8 + (sq.charCodeAt(0) - 97);
  const piece = pieces[idx];
  const mine = state.human === 'white' ? /[PRNBQK]/.test(piece) : /[prnbqk]/.test(piece);
  if (!selected) {
    if (mine) selected = sq;
    render();
    return;
  }
  if (selected === sq) { selected = null; render(); return; }
  if (mine) { selected = sq; render(); return; }
  let uci = selected + sq;
  const matches = state.legal.filter(m => m.slice(0,4) === uci);
  if (!matches.length) { selected = mine ? sq : null; render(); return; }
  if (needsPromo(selected, sq) || matches.length > 1) {
    const p = (prompt('Coronación: q r b n', 'q') || 'q').toLowerCase().slice(0,1);
    uci += 'qrbn'.includes(p) ? p : 'q';
  }
  selected = null;
  await submitMove(uci);
}

async function post(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {})
  });
  const data = await res.json();
  state = data;
  if (!res.ok) document.getElementById('msg').textContent = data.error || 'Error';
  render();
  return data;
}

async function awaitEngine(after) {
  if (!after || after.error || !after.engine_to_move) return;
  thinking = true;
  render();
  try {
    await post('/api/engine', {});
  } finally {
    thinking = false;
    render();
  }
}

async function submitMove(uci) {
  thinking = true;
  try {
    const after = await post('/api/move', {move: uci});
    await awaitEngine(after);
  } finally {
    thinking = false;
    render();
  }
}

async function newGame() {
  thinking = true;
  try {
    const after = await post('/api/new', {
      human: document.getElementById('color').value,
      movetime_ms: +document.getElementById('time').value
    });
    await awaitEngine(after);
  } finally {
    thinking = false;
    render();
  }
}

document.getElementById('new').onclick = () => newGame();
document.getElementById('undo').onclick = async () => { await post('/api/undo', {}); };
document.getElementById('hint').onclick = async () => {
  thinking = true; render();
  try { await post('/api/hint', {}); }
  finally { thinking = false; render(); }
};
document.getElementById('color').onchange = () => newGame();
document.getElementById('time').onchange = () => post('/api/settings', {
  movetime_ms: +document.getElementById('time').value
});

fetch('/api/state').then(r => r.json()).then(async s => {
  state = s;
  render();
  await awaitEngine(s);
});
</script>
</body>
</html>
"""


class PlayHandler(BaseHTTPRequestHandler):
    game: Game

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, payload: dict[str, Any], code: int = 200) -> None:
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode() or "{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = PLAY_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/state":
            self._json(self.game.snapshot())
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body = self._read_json()
        try:
            if path == "/api/new":
                human = body.get("human", self.game.human)
                if human not in ("white", "black"):
                    raise ValueError("color inválido")
                if "movetime_ms" in body:
                    self.game.movetime_ms = int(body["movetime_ms"])
                self.game.reset(human)
                self._json(self.game.snapshot())
                return
            if path == "/api/move":
                self.game.play_human(str(body.get("move", "")))
                self._json(self.game.snapshot())
                return
            if path == "/api/engine":
                self.game.maybe_engine_move()
                self._json(self.game.snapshot())
                return
            if path == "/api/undo":
                self.game.undo()
                self._json(self.game.snapshot())
                return
            if path == "/api/hint":
                self.game.hint()
                self._json(self.game.snapshot())
                return
            if path == "/api/settings":
                if "movetime_ms" in body:
                    self.game.movetime_ms = int(body["movetime_ms"])
                self._json(self.game.snapshot())
                return
        except ValueError as error:
            payload = self.game.snapshot()
            payload["error"] = str(error)
            payload["message"] = str(error)
            self._json(payload, 400)
            return
        self.send_error(404)


def find_engine(path: Path) -> Path:
    if path.exists():
        return path
    raise FileNotFoundError(
        f"No encuentro {path}. Compila primero:\n"
        "  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release\n"
        '  cmake --build build -j"$(nproc)"'
    )


def _eval_file(config: Path) -> str:
    if not config.exists():
        return ""
    for line in config.read_text().splitlines():
        if "EvalFile" in line:
            parts = line.split()
            if "value" in parts:
                return parts[parts.index("value") + 1]
    return ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Juega una partida contra NSCE")
    parser.add_argument("--engine", type=Path, default=ROOT / "build" / "nsce")
    parser.add_argument("--config", type=Path, default=ROOT / "tools" / "configs" / "baseline.uci")
    parser.add_argument("--color", choices=("white", "black"), default="white")
    parser.add_argument("--movetime", type=int, default=1000, help="ms por jugada del motor")
    parser.add_argument("--nodes", type=int, default=0, help="si >0, busca por nodos en vez de tiempo")
    parser.add_argument("--fen", default="startpos")
    parser.add_argument("--cli", action="store_true", help="tablero ASCII en terminal")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open",
        action="store_true",
        help="abrir el navegador después de escuchar (off por defecto: xdg-open puede colgar la sesión)",
    )
    parser.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.chdir(ROOT)
    engine_path = find_engine(args.engine)
    engine = UciEngine([str(engine_path)], name="nsce", cwd=ROOT)
    try:
        if args.config.exists():
            engine.apply_uci_file(args.config)
        game = Game(
            engine,
            human=args.color,
            movetime_ms=args.movetime,
            nodes=args.nodes,
            fen=args.fen,
        )
        net = _eval_file(args.config) or "internal"
        name = engine.identity.get("id_name") or "NSCE"
        game.label = f"{name} · 2200"
        print(f"{game.label}  net={net}  {args.movetime} ms/jugada", flush=True)
        if args.cli:
            run_cli(game)
            return 0
        game.maybe_engine_move()
        PlayHandler.game = game
        HTTPServer.allow_reuse_address = True
        try:
            server = HTTPServer(("127.0.0.1", args.port), PlayHandler)
        except OSError as error:
            print(f"No pude escuchar en 127.0.0.1:{args.port}: {error}", file=sys.stderr)
            print("Cierra el tablero anterior o pasa --port.", file=sys.stderr)
            return 1
        url = f"http://127.0.0.1:{args.port}/"
        print(f"NSCE listo. Abre {url}", flush=True)
        print("Ctrl+C para salir.", flush=True)
        if args.open and not args.no_browser:

            def _open_browser() -> None:
                time.sleep(0.4)
                webbrowser.open(url)

            threading.Thread(target=_open_browser, daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print()
        finally:
            server.server_close()
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
