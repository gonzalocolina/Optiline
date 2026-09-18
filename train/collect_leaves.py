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
import atexit
import json
import multiprocessing
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from uci_common import UciEngine, load_openings  # noqa: E402

DEFAULT_SITES = ("q_stand_pat", "static", "in_check_static")
FINISHED_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2"})
MIN_FREE_BYTES = 512 * 1024 * 1024


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
        self._db = sqlite3.connect(path, timeout=60.0)
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

    def commit(self) -> None:
        self._db.commit()
        self._pending = 0

    def _maybe_commit(self) -> None:
        self._pending += 1
        if self._pending >= 4096:
            self.commit()

    def close(self) -> None:
        self.commit()
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


def rewind_leaf_telemetry(engine: UciEngine, path: Path) -> None:
    """Close the engine stream, drop the raw dump, reopen. Keeps one search of telemetry on disk."""
    engine.apply_options({"LeafTelemetryFile": "<empty>"})
    path.write_bytes(b"")
    engine.apply_options({"LeafTelemetryFile": str(path)})


def stamp_payload(game: dict | None) -> dict | None:
    """Fields stamp_leaf needs. Do not pickle the full self-play game into workers."""
    if game is None:
        return None
    return {
        "opening_index": game.get("opening_index"),
        "color": game.get("color") or "as_written",
        "result": game.get("result"),
        "termination": game.get("termination"),
    }


def parse_telemetry_records(lines: list[str], game: dict | None, root_fen: str) -> list[dict]:
    records: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if game is not None:
            record = stamp_leaf(record, game, root_fen)
        else:
            record = dict(record)
            record["source"] = "leaf"
            record["label_kind"] = "search_leaf"
        records.append(record)
    return records


def search_root_leaves(
    engine: UciEngine,
    telemetry: Path,
    game: dict | None,
    fen: str,
    depth: int,
    nodes: int,
) -> list[dict]:
    engine.new_game()
    if depth > 0:
        engine.go_depth(fen, [], depth)
    else:
        engine.go_nodes(fen, [], nodes)
    lines, _ = consume_new_lines(telemetry, 0)
    rewind_leaf_telemetry(engine, telemetry)
    return parse_telemetry_records(lines, game, fen)


def ingest_records(
    handle,
    store: FenStore,
    sites: set[str],
    records: list[dict],
    game: dict | None,
    fen: str,
) -> int:
    added = 0
    for record in records:
        if not keep_leaf(record, sites, store):
            continue
        handle.write(json.dumps(record) + "\n")
        added += 1
    opening_index, color = game_token(game)
    store.add_root(opening_index, color, fen_key(fen))
    store.commit()
    handle.flush()
    return added


def repair_truncated_jsonl(path: Path) -> int:
    """Drop a partial last line left by a killed append. Returns bytes removed."""
    if not path.exists():
        return 0
    size = path.stat().st_size
    if size == 0:
        return 0
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        if handle.read(1) == b"\n":
            return 0
        found = -1
        pos = size
        chunk = 1024 * 1024
        while pos > 0:
            start = max(0, pos - chunk)
            handle.seek(start)
            data = handle.read(pos - start)
            idx = data.rfind(b"\n")
            if idx >= 0:
                found = start + idx + 1
                break
            pos = start
    keep = found if found >= 0 else 0
    dropped = size - keep
    os.truncate(path, keep)
    return dropped


def disk_too_full(path: Path, minimum: int = MIN_FREE_BYTES) -> bool:
    return shutil.disk_usage(path).free < minimum


_WORKER_ENGINE: UciEngine | None = None
_WORKER_TELEMETRY: Path | None = None


def _close_leaf_worker() -> None:
    global _WORKER_ENGINE, _WORKER_TELEMETRY
    engine, telemetry = _WORKER_ENGINE, _WORKER_TELEMETRY
    _WORKER_ENGINE = None
    _WORKER_TELEMETRY = None
    if engine is not None:
        try:
            engine.apply_options({"LeafTelemetryFile": "<empty>"})
        except OSError:
            pass
        engine.close()
    if telemetry is not None:
        telemetry.unlink(missing_ok=True)


def _init_leaf_worker(engine: str, config: str, telemetry_dir: str) -> None:
    global _WORKER_ENGINE, _WORKER_TELEMETRY
    _close_leaf_worker()
    telemetry = Path(telemetry_dir) / f"leaves.w{os.getpid()}.raw.jsonl"
    telemetry.unlink(missing_ok=True)
    _WORKER_TELEMETRY = telemetry
    _WORKER_ENGINE = UciEngine([engine], "NSCE")
    _WORKER_ENGINE.apply_uci_file(Path(config))
    _WORKER_ENGINE.apply_options({"LeafTelemetryFile": str(telemetry), "Threads": "1", "Hash": "16"})
    atexit.register(_close_leaf_worker)


def _search_job(job: dict) -> dict:
    assert _WORKER_ENGINE is not None and _WORKER_TELEMETRY is not None
    records = search_root_leaves(
        _WORKER_ENGINE,
        _WORKER_TELEMETRY,
        job["game"],
        str(job["fen"]),
        int(job["depth"]),
        int(job["nodes"]),
    )
    return {"seq": int(job["seq"]), "records": records}


def run_parallel_searches(
    jobs: list[dict],
    workers: int,
    engine: str,
    config: str,
    telemetry_dir: str,
    on_payload,
    should_stop,
) -> None:
    """Spawn workers (not fork) so the parent's sqlite handle is not inherited."""
    remaining: deque[dict] = deque(jobs)
    window = max(workers * 2, workers)
    retries: dict[int, int] = {}
    pool_deaths = 0
    ctx = multiprocessing.get_context("spawn")
    while remaining:
        if should_stop():
            return
        in_flight: dict = {}
        try:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=ctx,
                initializer=_init_leaf_worker,
                initargs=(engine, config, telemetry_dir),
            ) as pool:

                def submit_more() -> None:
                    while remaining and len(in_flight) < window and not should_stop():
                        job = remaining.popleft()
                        in_flight[pool.submit(_search_job, job)] = job

                submit_more()
                while in_flight:
                    if should_stop():
                        return
                    done, _ = wait(list(in_flight), timeout=1.0, return_when=FIRST_COMPLETED)
                    for future in done:
                        job = in_flight.pop(future)
                        try:
                            payload = future.result()
                        except Exception as exc:
                            seq = int(job["seq"])
                            retries[seq] = retries.get(seq, 0) + 1
                            log(f"leaf worker failed seq={seq}: {exc}")
                            if retries[seq] < 3:
                                remaining.append(job)
                            else:
                                log(f"skipping seq={seq} after {retries[seq]} failures")
                        else:
                            on_payload(payload)
                        submit_more()
        except BrokenProcessPool as exc:
            pool_deaths += 1
            log(f"leaf worker pool died ({exc}); respawning ({pool_deaths}/8)")
            remaining.extendleft(reversed(list(in_flight.values())))
            if pool_deaths >= 8:
                raise


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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel 1-thread engine processes for root searches (idle cores). "
        "Not Lazy SMP; uniqueness stays in this process via the sqlite index",
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be >= 1")

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

    if disk_too_full(output.parent):
        free = shutil.disk_usage(output.parent).free
        log(f"refusing: only {free} bytes free under {output.parent} (need ≥512MB)")
        store.close()
        return 1

    workers = min(args.workers, max(1, len(roots)))
    kept = 0
    started = time.monotonic()
    aborted = False
    mode = "a" if args.append else "w"
    if args.append:
        dropped = repair_truncated_jsonl(output)
        if dropped:
            log(f"dropped {dropped} truncated trailing bytes in {output}")

    def log_progress(done: int, game: dict | None, fen: str, added: int) -> None:
        elapsed = max(time.monotonic() - started, 1e-6)
        remaining = max(len(roots) - done, 0)
        eta = remaining * (elapsed / done) if done else 0.0
        label = (
            f"opening={game.get('opening_index')} {game.get('color')} result={game.get('result')}"
            if game
            else f"book {done} {fen_key(fen)}"
        )
        log(
            f"leaves {done}/{len(roots)} ({100.0 * done / max(len(roots), 1):.1f}%)  "
            f"{label}  +{added} unique  total {kept}  workers={workers}  "
            f"elapsed {format_duration(elapsed)}  eta {format_duration(eta)}"
        )

    try:
        with output.open(mode, encoding="utf-8") as handle:
            if workers <= 1:
                engine = UciEngine([str(args.engine)], "NSCE")
                try:
                    engine.apply_uci_file(Path(args.config))
                    if telemetry.exists():
                        telemetry.unlink()
                    engine.apply_options(
                        {"LeafTelemetryFile": str(telemetry), "Threads": "1", "Hash": "16"}
                    )
                    for index, (game, fen) in enumerate(roots, start=1):
                        if disk_too_full(output.parent):
                            free = shutil.disk_usage(output.parent).free
                            log(
                                f"stopping: only {free} bytes free under {output.parent} "
                                f"(need ≥512MB); rerun --append"
                            )
                            aborted = True
                            break
                        records = search_root_leaves(
                            engine, telemetry, game, fen, args.depth, args.nodes
                        )
                        added = ingest_records(handle, store, sites, records, game, fen)
                        kept += added
                        log_progress(index, game, fen, added)
                finally:
                    engine.close()
                    telemetry.unlink(missing_ok=True)
            else:
                log(
                    f"collect_leaves spawning {workers} engine processes "
                    f"(spawn, Threads=1 each, unique telemetry per worker)"
                )
                telemetry_dir = str(output.parent)
                jobs = [
                    {
                        "seq": seq,
                        "game": stamp_payload(game),
                        "fen": fen,
                        "depth": args.depth,
                        "nodes": args.nodes,
                    }
                    for seq, (game, fen) in enumerate(roots)
                ]
                done = 0

                def on_payload(payload: dict) -> None:
                    nonlocal kept, done, aborted
                    if aborted:
                        return
                    seq = int(payload["seq"])
                    game, fen = roots[seq]
                    added = ingest_records(
                        handle, store, sites, payload["records"], game, fen
                    )
                    kept += added
                    done += 1
                    log_progress(done, game, fen, added)
                    if disk_too_full(output.parent):
                        free = shutil.disk_usage(output.parent).free
                        log(
                            f"stopping: only {free} bytes free under {output.parent} "
                            f"(need ≥512MB); rerun --append"
                        )
                        aborted = True

                run_parallel_searches(
                    jobs,
                    workers,
                    str(args.engine),
                    str(args.config),
                    telemetry_dir,
                    on_payload,
                    lambda: aborted,
                )
    finally:
        store.close()

    log(f"wrote {kept} unique leaf FENs to {output}" + ("  aborted" if aborted else ""))
    if aborted:
        return 1
    return 0 if kept or args.append else 1


if __name__ == "__main__":
    raise SystemExit(main())
