#!/usr/bin/env python3
"""Dump the positions the tree actually evaluates (QS stand-pat, static, checks).

Root FEN dumps are the wrong exam. This records LeafTelemetryFile rows from the
frozen baseline so later static labels look like search leaves.

`--games` searches path positions of finished self-play games. Game WDL is
copied only onto the search root (played path). Hypothetical leaves keep
provenance (`source_game`, `opening_index`) and stay unlabeled.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402

DEFAULT_SITES = ("q_stand_pat", "static", "in_check_static")
FINISHED_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2"})


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def fen_key(fen: str) -> str:
    return " ".join(str(fen).split()[:4])


def load_games(path: Path) -> list[dict]:
    games: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            games.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return games


def load_finished_games(path: Path) -> list[dict]:
    return [game for game in load_games(path) if game.get("result") in FINISHED_RESULTS]


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


def path_fen_keys(game: dict) -> set[str]:
    keys = {fen_key(str(game.get("fen") or ""))}
    keys.discard("")
    for rec in game.get("records") or []:
        key = fen_key(str(rec.get("fen") or ""))
        if key:
            keys.add(key)
    return keys


def game_token(game: dict | None) -> tuple[object, str]:
    game = game or {}
    return game.get("opening_index"), str(game.get("color") or "as_written")


def path_index_from_games(games: list[dict]) -> dict[tuple[object, str], set[str]]:
    return {game_token(game): path_fen_keys(game) for game in games}


def stamp_leaf(record: dict, game: dict, root_fen: str) -> dict:
    opening_index = game.get("opening_index")
    color = game.get("color") or "as_written"
    record = dict(record)
    record.pop("result", None)
    record["source"] = "leaf"
    record["termination"] = game.get("termination")
    record["source_game"] = f"selfplay:{opening_index}"
    record["opening_index"] = opening_index
    record["color"] = color
    is_path = fen_key(str(record.get("fen") or "")) == fen_key(root_fen)
    record["label_kind"] = "path" if is_path else "search_leaf"
    result = game.get("result")
    if is_path and result in FINISHED_RESULTS:
        record["result"] = result
    return record


def apply_honest_result(record: dict, index: dict[tuple[object, str], set[str]]) -> dict:
    """Keep WDL only when this FEN was played in the source game."""
    record = dict(record)
    token = (record.get("opening_index"), str(record.get("color") or "as_written"))
    keys = index.get(token, set())
    fen = fen_key(str(record.get("fen") or ""))
    if fen and fen in keys:
        record["label_kind"] = "path"
        if record.get("result") not in FINISHED_RESULTS:
            record.pop("result", None)
    else:
        record["label_kind"] = "search_leaf"
        record.pop("result", None)
    return record


def strip_leaf_results(games_path: Path, leaves_path: Path, output_path: Path) -> dict[str, int]:
    index = path_index_from_games(load_finished_games(games_path))
    stats = {"records": 0, "path": 0, "search_leaf": 0, "with_result": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path
    tmp_handle = None
    if output_path.resolve() == leaves_path.resolve():
        tmp_handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=str(output_path.parent), suffix=".jsonl"
        )
        tmp_path = Path(tmp_handle.name)
    handle = tmp_handle or tmp_path.open("w", encoding="utf-8")
    try:
        with leaves_path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record = apply_honest_result(record, index)
                stats["records"] += 1
                kind = record.get("label_kind")
                if kind == "path":
                    stats["path"] += 1
                else:
                    stats["search_leaf"] += 1
                if record.get("result") in FINISHED_RESULTS:
                    stats["with_result"] += 1
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    finally:
        handle.close()
    if tmp_handle is not None:
        tmp_path.replace(output_path)
    return stats


def played_path_fens(game: dict) -> list[str]:
    fens = [str(game["fen"])]
    for rec in game.get("records") or []:
        fen = rec.get("fen")
        if not fen:
            continue
        if fen_key(str(fen)) == fen_key(fens[-1]):
            continue
        fens.append(str(fen))
    return fens


def path_records_from_games(games: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for game in games:
        if game.get("result") not in FINISHED_RESULTS:
            continue
        for fen in played_path_fens(game):
            key = fen_key(fen)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(stamp_leaf({"fen": fen, "site": "path"}, game, fen))
    return rows


def write_path_records(games_path: Path, output_path: Path) -> int:
    rows = path_records_from_games(load_finished_games(games_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return len(rows)


def index_existing_leaves(
    leaves_path: Path,
    sqlite_path: Path,
    games_path: Path | None = None,
    positions_per_game: int = 3,
) -> dict[str, int]:
    store = FenStore(sqlite_path)
    stats = {"fen_keys": 0, "roots": 0}
    try:
        with leaves_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = fen_key(str(record.get("fen") or ""))
                if key and store.add_fen(key):
                    stats["fen_keys"] += 1
        if games_path is not None and games_path.exists():
            for game in load_finished_games(games_path):
                opening_index, color = game_token(game)
                for fen in roots_from_game(game, positions_per_game):
                    store.add_root(opening_index, color, fen_key(fen))
                    stats["roots"] += 1
    finally:
        store.close()
    return stats


class FenStore:
    """On-disk fen_key and collected-root index so leaf dumps can append."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS fen_keys (k TEXT PRIMARY KEY)")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS collected_roots ("
            "opening_index TEXT NOT NULL, color TEXT NOT NULL, root_key TEXT NOT NULL, "
            "PRIMARY KEY (opening_index, color, root_key))"
        )
        self._db.commit()
        self._pending = 0

    def add_fen(self, key: str) -> bool:
        try:
            self._db.execute("INSERT INTO fen_keys (k) VALUES (?)", (key,))
        except sqlite3.IntegrityError:
            return False
        self._maybe_commit()
        return True

    def has_root(self, opening_index: object, color: str, root_key: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM collected_roots WHERE opening_index = ? AND color = ? AND root_key = ? LIMIT 1",
            (str(opening_index), color, root_key),
        ).fetchone()
        return row is not None

    def add_root(self, opening_index: object, color: str, root_key: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO collected_roots (opening_index, color, root_key) VALUES (?, ?, ?)",
            (str(opening_index), color, root_key),
        )
        self._maybe_commit()

    def _maybe_commit(self) -> None:
        self._pending += 1
        if self._pending >= 4096:
            self._db.commit()
            self._pending = 0

    def close(self) -> None:
        self._db.commit()
        self._db.close()


def keep_leaf(record: dict, sites: set[str], seen: set[str] | FenStore) -> bool:
    site = str(record.get("site") or "")
    if sites and site not in sites:
        return False
    key = fen_key(str(record.get("fen") or ""))
    if not key:
        return False
    if isinstance(seen, FenStore):
        return seen.add_fen(key)
    if key in seen:
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
        help="selfplay JSONL; dump leaves from finished games",
    )
    parser.add_argument(
        "--positions-per-game",
        type=int,
        default=3,
        help="with --games, search this many path positions per finished game",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="append unique leaves; skip roots already in the sqlite index",
    )
    parser.add_argument(
        "--seen-sqlite",
        default="",
        help="fen_key / collected-root sqlite (default: output with .seen.sqlite)",
    )
    parser.add_argument(
        "--strip-results",
        action="store_true",
        help="rewrite --leaves so only played-path FENs keep game WDL",
    )
    parser.add_argument(
        "--leaves",
        default="",
        help="leaf JSONL for --strip-results (default: --output)",
    )
    parser.add_argument(
        "--path-output",
        default="",
        help="write played-path FENs with honest results from --games; no search",
    )
    parser.add_argument(
        "--index-existing",
        action="store_true",
        help="fill --seen-sqlite from --output/--leaves and mark --games roots collected",
    )
    args = parser.parse_args()

    if args.strip_results:
        if not args.games:
            parser.error("--strip-results needs --games")
        if args.leaves:
            leaves = Path(args.leaves)
            output = Path(args.output) if args.output != parser.get_default("output") else leaves
        else:
            leaves = output = Path(args.output)
        stats = strip_leaf_results(Path(args.games), leaves, output)
        log(
            f"strip_leaf_results {stats['records']} records  "
            f"path={stats['path']} search_leaf={stats['search_leaf']} "
            f"with_result={stats['with_result']}  -> {output}"
        )
        return 0 if stats["records"] else 1

    if args.path_output:
        if not args.games:
            parser.error("--path-output needs --games")
        written = write_path_records(Path(args.games), Path(args.path_output))
        log(f"wrote {written} path FENs to {args.path_output}")
        return 0 if written else 1

    if args.index_existing:
        leaves = Path(args.leaves or args.output)
        sqlite_path = Path(args.seen_sqlite) if args.seen_sqlite else leaves.with_suffix(".seen.sqlite")
        games_path = Path(args.games) if args.games else None
        stats = index_existing_leaves(leaves, sqlite_path, games_path, args.positions_per_game)
        log(
            f"index_existing fen_keys={stats['fen_keys']} roots={stats['roots']}  -> {sqlite_path}"
        )
        return 0 if stats["fen_keys"] else 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    telemetry = output.with_suffix(".raw.jsonl")
    sqlite_path = Path(args.seen_sqlite) if args.seen_sqlite else output.with_suffix(".seen.sqlite")
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
            + ("  append" if args.append else "")
        )
    else:
        openings = load_openings(Path(args.openings))[: max(1, args.limit)]
        roots = [(None, fen) for fen in openings]
        log(f"collect_leaves {len(roots)} openings  nodes={args.nodes}")

    if not args.append and sqlite_path.exists():
        sqlite_path.unlink()
    store = FenStore(sqlite_path)
    skipped = 0
    pending: list[tuple[dict | None, str]] = []
    for game, fen in roots:
        opening_index, color = game_token(game)
        if args.append and store.has_root(opening_index, color, fen_key(fen)):
            skipped += 1
            continue
        pending.append((game, fen))
    if skipped:
        log(f"skip {skipped} already-collected roots  remaining {len(pending)}")
    roots = pending

    engine = UciEngine([str(args.engine)], "NSCE")
    kept = 0
    offset = 0
    started = time.monotonic()
    try:
        engine.apply_uci_file(Path(args.config))
        if telemetry.exists():
            telemetry.unlink()
        engine.apply_options({"LeafTelemetryFile": str(telemetry), "Threads": "1", "Hash": "16"})
        mode = "a" if args.append else "w"
        with output.open(mode, encoding="utf-8") as handle:
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
                        record = stamp_leaf(record, game, fen)
                    else:
                        record["source"] = "leaf"
                        record["label_kind"] = "search_leaf"
                    if not keep_leaf(record, sites, store):
                        continue
                    handle.write(json.dumps(record) + "\n")
                    kept += 1
                    added += 1
                opening_index, color = game_token(game)
                store.add_root(opening_index, color, fen_key(fen))
                handle.flush()
                elapsed = max(time.monotonic() - started, 1e-6)
                eta = (len(roots) - index) * (elapsed / index) if index else 0.0
                label = (
                    f"opening={game.get('opening_index')} {game.get('color')} result={game.get('result')}"
                    if game
                    else f"book {index}"
                )
                log(
                    f"leaves {index}/{len(roots)} ({100.0 * index / max(len(roots), 1):.1f}%)  "
                    f"{label}  +{added} unique  total {kept}  "
                    f"elapsed {format_duration(elapsed)}  eta {format_duration(eta)}"
                )
    finally:
        engine.close()
        store.close()

    log(f"wrote {kept} unique leaf FENs to {output}")
    return 0 if kept or args.append else 1


if __name__ == "__main__":
    raise SystemExit(main())
