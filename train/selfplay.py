#!/usr/bin/env python3
"""Self-play with real game outcomes (checkmate / stalemate / draw / adjudication).

Reward: result_from_white - lambda * (mean_nodes / scale), under fixed movetime.
"""

from __future__ import annotations

import argparse
import atexit
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402


def color_flip_fen(fen: str) -> str:
    """Swap colors, ranks, side to move, castling, and ep. White-POV result flips with the board."""
    parts = fen.split()
    if len(parts) < 4:
        raise ValueError(f"invalid FEN: {fen}")
    placement, stm, castle, ep = parts[0], parts[1], parts[2], parts[3]
    half = parts[4] if len(parts) > 4 else "0"
    full = parts[5] if len(parts) > 5 else "1"
    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError(f"invalid FEN placement: {fen}")
    flipped_ranks = []
    for rank in reversed(ranks):
        flipped_ranks.append("".join(char.swapcase() if char.isalpha() else char for char in rank))
    new_stm = "b" if stm == "w" else "w"
    if castle == "-":
        new_castle = "-"
    else:
        translated = castle.translate(str.maketrans("KQkq", "kqKQ"))
        new_castle = "".join(char for char in "KQkq" if char in translated) or "-"
    if ep == "-":
        new_ep = "-"
    else:
        new_ep = f"{ep[0]}{9 - int(ep[1])}"
    return f"{'/'.join(flipped_ranks)} {new_stm} {new_castle} {new_ep} {half} {full}"


def game_schedule(openings: list[str], games: int, both_colors: bool) -> list[tuple[int, str, str]]:
    """Return (opening_index, fen, color_tag) for each self-play game."""
    if not openings:
        raise ValueError("need at least one opening")
    rows: list[tuple[int, str, str]] = []
    if not both_colors:
        for index in range(games):
            opening_index = index % len(openings)
            rows.append((opening_index, openings[opening_index], "as_written"))
        return rows
    if games % 2:
        raise ValueError("--both-colors requires an even --games so each opening is paired")
    for index in range(games):
        opening_index = (index // 2) % len(openings)
        fen = openings[opening_index]
        if index % 2 == 1:
            rows.append((opening_index, color_flip_fen(fen), "flipped"))
        else:
            rows.append((opening_index, fen, "as_written"))
    return rows


def terminal_result(status: str, ply: int) -> tuple[str | None, str]:
    """PGN result for a finished game, or None if the engine is still playing.

    Hitting max_plies is not a draw: labeling those 1/2-1/2 poisons WDL mix.
    `ply` is 0-based index of the move that just landed.
    """
    if status == "checkmate":
        return ("1-0" if ply % 2 == 0 else "0-1"), "checkmate"
    if status in {"stalemate", "draw"}:
        return "1/2-1/2", status
    return None, "ongoing"


def format_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds or seconds == float("inf"):
        return "?"
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def play_game(
    engine: UciEngine,
    fen: str,
    movetime: int,
    max_plies: int,
    lam: float,
    on_ply: object | None = None,
) -> dict:
    engine.new_game()
    moves: list[str] = []
    records = []
    total_nodes = 0
    result: str | None = None
    termination = "max_plies"
    for ply in range(max_plies):
        mv = engine.go_movetime(fen, moves, movetime)
        total_nodes += engine.last_nodes
        if mv in ("0000", "(none)", "none"):
            status = engine.status(fen, moves)
            result, termination = terminal_result(status, max(0, len(moves) - 1))
            if result is None:
                termination = "no_move"
            break
        records.append({"ply": ply, "move": mv, "fen": engine.current_fen(fen, moves), "nodes": engine.last_nodes})
        moves.append(mv)
        if on_ply is not None:
            on_ply(len(moves), max_plies, mv)
        result, termination = terminal_result(engine.status(fen, moves), ply)
        if result is not None:
            break
    else:
        termination = "max_plies"
        result = None
    score_white = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}.get(result)
    mean_nodes = total_nodes / max(1, len(moves))
    reward = (0.5 if score_white is None else score_white) - lam * (mean_nodes / 10000.0)
    return {
        "fen": fen,
        "moves": moves,
        "records": records,
        "result": result,
        "termination": termination,
        "score_white": score_white,
        "reward": reward,
        "total_nodes": total_nodes,
        "mean_nodes": mean_nodes,
    }


def position_payload(fen: str, game: dict, source_game: str, ply: int, phase: str | None = None) -> dict:
    payload = {
        "fen": fen,
        "source_game": source_game,
        "ply": ply,
        "termination": game["termination"],
    }
    if game.get("result") is not None:
        payload["result"] = game["result"]
    if phase is not None:
        payload["phase"] = phase
    return payload


def load_games(path: Path) -> list[dict]:
    """Load complete JSONL games; drop a truncated last line."""
    if not path.exists():
        return []
    games: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            games.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return games


def completed_schedule_indices(games: list[dict]) -> set[int]:
    """Schedule slots already on disk.

    Serial dumps before `--workers` have no `schedule_index`; those occupy
    0..n-1 in file order. Parallel dumps stamp the index so resume can skip
    holes if games finish out of order.
    """
    completed: set[int] = set()
    legacy = 0
    for game in games:
        if "schedule_index" in game:
            completed.add(int(game["schedule_index"]))
        else:
            completed.add(legacy)
            legacy += 1
    return completed


_WORKER_ENGINE: UciEngine | None = None


def _close_worker() -> None:
    global _WORKER_ENGINE
    if _WORKER_ENGINE is not None:
        _WORKER_ENGINE.close()
        _WORKER_ENGINE = None


def _init_worker(engine: str, config: str) -> None:
    global _WORKER_ENGINE
    _close_worker()
    _WORKER_ENGINE = UciEngine([engine], "NSCE")
    _WORKER_ENGINE.apply_uci_file(Path(config))
    atexit.register(_close_worker)


def _play_job(job: dict) -> dict:
    assert _WORKER_ENGINE is not None
    game_no = int(job["done"])
    games = int(job["games"])
    max_plies = int(job["max_plies"])
    progress_plies = int(job["progress_plies"])

    def on_ply(ply_done: int, max_plies: int, move: str) -> None:
        if progress_plies <= 0 or ply_done % progress_plies:
            return
        log(f"selfplay {game_no}/{games}  ply {ply_done}/{max_plies}  last {move}")

    game_started = time.monotonic()
    game = play_game(
        _WORKER_ENGINE,
        str(job["fen"]),
        int(job["movetime"]),
        max_plies,
        float(job["lam"]),
        on_ply=on_ply,
    )
    game["opening_index"] = job["opening_index"]
    game["color"] = job["color"]
    game["schedule_index"] = int(job["schedule_index"])
    game["play_seconds"] = time.monotonic() - game_started
    return game


def positions_from_game(game: dict) -> list[dict]:
    opening_index = int(game.get("opening_index") or 0)
    source_game = f"selfplay:{opening_index}"
    rows = [position_payload(str(game["fen"]), game, source_game, 0, "opening")]
    for rec in game.get("records") or []:
        rec_fen = rec.get("fen")
        if not rec_fen:
            continue
        rows.append(position_payload(str(rec_fen), game, source_game, int(rec.get("ply") or 0)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--movetime", type=int, default=50)
    ap.add_argument(
        "--max-plies",
        type=int,
        default=200,
        help="stop without a result rather than labeling a cutoff as 1/2-1/2",
    )
    ap.add_argument(
        "--both-colors",
        action="store_true",
        help="play each opening as written and color-flipped (even --games)",
    )
    ap.add_argument(
        "--progress-plies",
        type=int,
        default=25,
        help="print a ply heartbeat every N moves while a game is running (0 disables)",
    )
    ap.add_argument("--lambda", dest="lam", type=float, default=0.1)
    ap.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    ap.add_argument("-o", "--output", default=str(ROOT / "train/data/selfplay.jsonl"))
    ap.add_argument(
        "--positions-out",
        default="",
        help="optional JSONL of (fen, result) for eval training; not random walks",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="append from existing -o games instead of starting over",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel 1-thread engine processes (idle cores). Not Lazy SMP; "
        "each game still uses Threads=1 / Hash 16 from the UCI config",
    )
    args = ap.parse_args()
    if args.workers < 1:
        ap.error("--workers must be >= 1")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    openings = load_openings(ROOT / "tools" / "openings_balanced.epd")
    try:
        schedule = game_schedule(openings, args.games, args.both_colors)
    except ValueError as error:
        ap.error(str(error))
    existing = load_games(out) if args.resume else []
    completed = completed_schedule_indices(existing) if args.resume else set()
    if len(completed) >= args.games:
        log(f"{out} already has {len(existing)} games (>= {args.games})")
        return 0
    if args.resume:
        out.write_text("".join(json.dumps(game) + "\n" for game in existing), encoding="utf-8")
    positions_path = Path(args.positions_out) if args.positions_out else None
    if positions_path is not None:
        positions_path.parent.mkdir(parents=True, exist_ok=True)
        with positions_path.open("w", encoding="utf-8") as handle:
            for game in existing:
                for row in positions_from_game(game):
                    handle.write(json.dumps(row) + "\n")
    jobs: list[dict] = []
    for index, (opening_index, fen, color_tag) in enumerate(schedule):
        if index in completed:
            continue
        jobs.append(
            {
                "schedule_index": index,
                "done": index + 1,
                "games": args.games,
                "opening_index": opening_index,
                "fen": fen,
                "color": color_tag,
                "movetime": args.movetime,
                "max_plies": args.max_plies,
                "lam": args.lam,
                "progress_plies": args.progress_plies,
            }
        )
    workers = min(args.workers, max(1, len(jobs)))
    log(
        f"selfplay {args.games} games  movetime={args.movetime}ms  "
        f"max_plies={args.max_plies}  both_colors={args.both_colors}  "
        f"openings={len(openings)}  workers={workers}  remaining={len(jobs)}"
        + (f"  resume {len(existing)}" if existing else "")
    )
    positions_handle = positions_path.open("a", encoding="utf-8") if positions_path is not None else None
    started = time.monotonic()
    results = Counter(game.get("result") or "*" for game in existing)
    terminations = Counter(str(game.get("termination") or "unknown") for game in existing)
    positions_written = sum(len(positions_from_game(game)) for game in existing)
    have = len(existing)
    newly = 0

    def record_game(handle, game: dict, game_started: float) -> None:
        nonlocal have, newly, positions_written
        handle.write(json.dumps(game) + "\n")
        handle.flush()
        results[game["result"] or "*"] += 1
        terminations[game["termination"]] += 1
        have += 1
        newly += 1
        elapsed = max(time.monotonic() - started, 1e-6)
        remaining = max(len(jobs) - newly, 0)
        eta = remaining * (elapsed / newly)
        pct = 100.0 * have / args.games
        game_s = float(game.get("play_seconds") or (time.monotonic() - game_started))
        done = int(game.get("schedule_index") or 0) + 1
        log(
            f"selfplay {done}/{args.games} ({pct:.1f}%)  "
            f"opening={game.get('opening_index')} {game.get('color')}  "
            f"result={game['result'] or '*'} {game['termination']}  "
            f"{len(game['moves'])} plies in {format_duration(game_s)}  "
            f"elapsed {format_duration(elapsed)}  eta {format_duration(eta)}  "
            f"on disk {have}/{args.games}"
        )
        log(
            f"  running 1-0:{results['1-0']}  0-1:{results['0-1']}  "
            f"draw:{results['1/2-1/2']}  unfinished:{results['*']}  "
            f"mates:{terminations['checkmate']}  "
            f"max_plies:{terminations['max_plies']}"
        )
        if positions_handle is not None:
            for row in positions_from_game(game):
                positions_handle.write(json.dumps(row) + "\n")
                positions_written += 1
            positions_handle.flush()

    try:
        with out.open("a" if args.resume else "w") as handle:
            if workers <= 1:
                eng = UciEngine([args.engine], "NSCE")
                eng.apply_uci_file(Path(args.config))
                try:
                    for job in jobs:
                        done = int(job["done"])
                        log(
                            f"selfplay {done}/{args.games} starting  "
                            f"opening={job['opening_index']} color={job['color']}"
                        )

                        def on_ply(
                            ply_done: int,
                            max_plies: int,
                            move: str,
                            game_no: int = done,
                        ) -> None:
                            if args.progress_plies <= 0 or ply_done % args.progress_plies:
                                return
                            log(f"selfplay {game_no}/{args.games}  ply {ply_done}/{max_plies}  last {move}")

                        game_started = time.monotonic()
                        game = play_game(
                            eng,
                            str(job["fen"]),
                            args.movetime,
                            args.max_plies,
                            args.lam,
                            on_ply=on_ply,
                        )
                        game["opening_index"] = job["opening_index"]
                        game["color"] = job["color"]
                        game["schedule_index"] = int(job["schedule_index"])
                        game["play_seconds"] = time.monotonic() - game_started
                        record_game(handle, game, game_started)
                finally:
                    eng.close()
            else:
                log(f"selfplay spawning {workers} engine processes (Threads=1 each)")
                with ProcessPoolExecutor(
                    max_workers=workers,
                    initializer=_init_worker,
                    initargs=(str(args.engine), str(args.config)),
                ) as pool:
                    pending = {pool.submit(_play_job, job): job for job in jobs}
                    for future in as_completed(pending):
                        game = future.result()
                        record_game(handle, game, time.monotonic())
    finally:
        if positions_handle is not None:
            positions_handle.close()
    log(
        f"selfplay done  {args.games} games in {format_duration(time.monotonic() - started)}  "
        f"1-0:{results['1-0']}  0-1:{results['0-1']}  draw:{results['1/2-1/2']}  "
        f"unfinished:{results['*']}  workers={workers}  wrote {out}"
    )
    if positions_path is not None:
        log(f"wrote {positions_written} positions to {positions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
