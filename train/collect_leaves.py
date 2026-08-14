#!/usr/bin/env python3
"""Dump the positions the tree actually evaluates (QS stand-pat, static, checks).

Root FEN dumps are the wrong exam. This records LeafTelemetryFile rows from the
frozen baseline so later static labels look like search leaves. `--games` stamps
a finished self-play result onto those leaves.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402

DEFAULT_SITES = ("q_stand_pat", "static", "in_check_static")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def fen_key(fen: str) -> str:
    return " ".join(str(fen).split()[:4])


def load_finished_games(path: Path) -> list[dict]:
    games: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            game = json.loads(line)
        except json.JSONDecodeError:
            break
        if game.get("result") in {"1-0", "0-1", "1/2-1/2"}:
            games.append(game)
    return games


def roots_from_game(game: dict, positions_per_game: int) -> list[str]:
    """Opening plus evenly spaced positions from the played path."""
    roots = [str(game["fen"])]
    records = [rec for rec in game.get("records") or [] if rec.get("fen")]
    extra = max(int(positions_per_game) - 1, 0)
    if extra <= 0 or not records:
        return roots
    last = len(records) - 1
    for step in range(1, extra + 1):
        index = min(last, (step * last) // extra)
        fen = str(records[index]["fen"])
        if fen_key(fen) != fen_key(roots[-1]):
            roots.append(fen)
    return roots


def stamp_leaf(record: dict, game: dict) -> dict:
    opening_index = game.get("opening_index")
    color = game.get("color") or "as_written"
    record = dict(record)
    record["source"] = "leaf"
    record["result"] = game["result"]
    record["termination"] = game.get("termination")
    record["source_game"] = f"selfplay:{opening_index}"
    record["opening_index"] = opening_index
    record["color"] = color
    return record


def keep_leaf(record: dict, sites: set[str], seen: set[str]) -> bool:
    site = str(record.get("site") or "")
    if sites and site not in sites:
        return False
    key = fen_key(str(record.get("fen") or ""))
    if not key or key in seen:
        return False
    seen.add(key)
    return True


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


def consume_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    if not path.exists():
        return [], offset
    with path.open("rb") as handle:
        handle.seek(offset)
        raw = handle.read()
        offset = handle.tell()
    text = raw.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    return lines, offset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    parser.add_argument("--config", default=str(ROOT / "tools/configs/baseline.uci"))
    parser.add_argument("--openings", default=str(ROOT / "tools" / "openings_balanced.epd"))
    parser.add_argument("--output", default=str(ROOT / "train/data/leaves.jsonl"))
    parser.add_argument("--nodes", type=int, default=25000)
    parser.add_argument("--depth", type=int, default=0, help="if >0, go depth instead of nodes")
    parser.add_argument(
        "--limit",
        type=int,
        default=64,
        help="max book openings, or max finished games with --games; 0 means all",
    )
    parser.add_argument(
        "--sites",
        default=",".join(DEFAULT_SITES),
        help="comma-separated LeafTelemetry sites to keep",
    )
    parser.add_argument(
        "--games",
        default="",
        help="selfplay JSONL; dump leaves from finished games and stamp result",
    )
    parser.add_argument(
        "--positions-per-game",
        type=int,
        default=3,
        help="with --games, search this many path positions per finished game",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    telemetry = output.with_suffix(".raw.jsonl")
    sites = {item.strip() for item in args.sites.split(",") if item.strip()}

    roots: list[tuple[dict | None, str]] = []
    if args.games:
        games = load_finished_games(Path(args.games))
        if args.limit > 0:
            games = games[: args.limit]
        for game in games:
            for fen in roots_from_game(game, args.positions_per_game):
                roots.append((game, fen))
        log(
            f"collect_leaves {len(games)} finished games  "
            f"{len(roots)} searches  nodes={args.nodes}  sites={','.join(sorted(sites))}"
        )
    else:
        openings = load_openings(Path(args.openings))[: max(1, args.limit)]
        roots = [(None, fen) for fen in openings]
        log(f"collect_leaves {len(roots)} openings  nodes={args.nodes}")

    engine = UciEngine([str(args.engine)], "NSCE")
    seen: set[str] = set()
    kept = 0
    offset = 0
    started = time.monotonic()
    try:
        engine.apply_uci_file(Path(args.config))
        if telemetry.exists():
            telemetry.unlink()
        engine.apply_options({"LeafTelemetryFile": str(telemetry), "Threads": "1", "Hash": "16"})
        with output.open("w", encoding="utf-8") as handle:
            for index, (game, fen) in enumerate(roots, start=1):
                engine.new_game()
                if args.depth > 0:
                    engine.go_depth(fen, [], args.depth)
                else:
                    engine.go_nodes(fen, [], args.nodes)
                lines, offset = consume_new_lines(telemetry, offset)
                added = 0
                for line in lines:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if game is not None:
                        record = stamp_leaf(record, game)
                    else:
                        record["source"] = "leaf"
                    if not keep_leaf(record, sites, seen):
                        continue
                    handle.write(json.dumps(record) + "\n")
                    kept += 1
                    added += 1
                handle.flush()
                elapsed = max(time.monotonic() - started, 1e-6)
                eta = (len(roots) - index) * (elapsed / index)
                label = (
                    f"opening={game.get('opening_index')} {game.get('color')} result={game.get('result')}"
                    if game
                    else f"book {index}"
                )
                log(
                    f"leaves {index}/{len(roots)} ({100.0 * index / len(roots):.1f}%)  "
                    f"{label}  +{added} unique  total {kept}  "
                    f"elapsed {format_duration(elapsed)}  eta {format_duration(eta)}"
                )
    finally:
        engine.close()

    log(f"wrote {kept} unique leaf FENs to {output}")
    return 0 if kept else 1


if __name__ == "__main__":
    raise SystemExit(main())
