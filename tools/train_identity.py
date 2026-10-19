#!/usr/bin/env python3
"""Dataset identity for Bullet training.

A shuffled file is reusable only when it has the same size as the source and
the sidecar records that source's SHA-256. Equal length is not identity: a
replacement gen0.bin with the same record count must be shuffled again.

Validation positions have to come from games that are absent from the training
file. extra[3] is the little-endian game id written by datagen. Files whose
extra bytes are all zero predate that stamp and cannot be split by game.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

RECORD = 32
EXTRA_OFFSET = 29
TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from experiment_common import sha256_file, write_manifest  # noqa: E402


def shuffle_decision(
    source_sha: str,
    source_bytes: int,
    shuffled_bytes: int | None,
    sidecar_sha: str | None,
    validate_ok: bool,
) -> str:
    """Return 'reuse' or 'reshuffle'."""
    if (
        shuffled_bytes is not None
        and shuffled_bytes == source_bytes
        and sidecar_sha == source_sha
        and validate_ok
    ):
        return "reuse"
    return "reshuffle"


def read_sidecar(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "source_sha256" not in data:
        return None
    return data


def write_sidecar(source: Path, sidecar: Path) -> dict:
    payload = {
        "source_sha256": sha256_file(source),
        "source_bytes": source.stat().st_size,
        "source_path": str(source.resolve()),
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def expected_graph_id(graph: str, wdl: str) -> str:
    proportion = f"{float(wdl):.4f}"
    if graph == "simple":
        return f"simple hidden=512 buckets=0 screlu=1 wdl={proportion}"
    if graph == "hl":
        return f"hl ft=512 hl=32 buckets=0 screlu=2 wdl={proportion}"
    if graph != "mlp":
        raise ValueError(f"unknown graph {graph}")
    return (
        f"mlp l1=512 l2=32 l3=32 buckets=8 pair=crelu*crelu skip=1 wdl={proportion}"
    )


def effective_parameters(graph: str, env: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if env is None else env
    smoke = "NSCE_SMOKE" in env
    return {
        "graph": graph,
        "wdl": env.get("NSCE_WDL", "0.0"),
        "batch": env.get("NSCE_BATCH", "8192"),
        "batches_per_superbatch": env.get("NSCE_BATCHES", "2" if smoke else "12208"),
        "superbatches": env.get("NSCE_SUPERBATCHES", "1" if smoke else "320"),
        # MLP and simple hardcode 0.001. Only the HL graph reads NSCE_LR.
        "lr": env.get("NSCE_LR", "0.0002") if graph == "hl" else "0.001",
        "skip": "1" if graph == "mlp" else "n/a",
        "resume": "0" if env.get("NSCE_RESUME") == "0" else "1",
        "test_set": env.get("NSCE_TEST_SET", ""),
        "test_freq": env.get("NSCE_TEST_FREQ", "32"),
        "smoke": "1" if smoke else "0",
    }


def game_id(record: bytes) -> int:
    if len(record) != RECORD:
        raise ValueError(f"bullet record is {len(record)} bytes, expected {RECORD}")
    extra = record[EXTRA_OFFSET : EXTRA_OFFSET + 3]
    return extra[0] | (extra[1] << 8) | (extra[2] << 16)


def iter_game_ids(path: Path):
    with path.open("rb") as handle:
        while True:
            record = handle.read(RECORD)
            if not record:
                return
            yield game_id(record)


def game_relation(train: Path, test: Path) -> str:
    """'disjoint', 'overlap', or 'unmarked' when every extra byte is zero."""
    train_ids = set(iter_game_ids(train))
    test_ids = set(iter_game_ids(test))
    if train_ids <= {0} and test_ids <= {0}:
        return "unmarked"
    if train_ids & test_ids:
        return "overlap"
    return "disjoint"


def split_games(source: Path, train: Path, test: Path, fraction: float, seed: int) -> dict[str, int]:
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be between 0 and 1")
    ids = sorted(set(iter_game_ids(source)))
    if ids == [0] or ids == []:
        raise ValueError(
            f"{source} has no game ids. Datagen stamps extra[3]; this file cannot be split by game."
        )
    order = list(ids)
    random.Random(seed).shuffle(order)
    n_test = max(1, int(round(len(order) * fraction)))
    if n_test >= len(order):
        raise ValueError("fraction leaves no training games")
    held = set(order[:n_test])
    train.parent.mkdir(parents=True, exist_ok=True)
    test.parent.mkdir(parents=True, exist_ok=True)
    n_train = n_test_pos = 0
    with source.open("rb") as src, train.open("wb") as train_out, test.open("wb") as test_out:
        while True:
            record = src.read(RECORD)
            if not record:
                break
            if game_id(record) in held:
                test_out.write(record)
                n_test_pos += 1
            else:
                train_out.write(record)
                n_train += 1
    return {
        "games": len(ids),
        "test_games": len(held),
        "train_positions": n_train,
        "test_positions": n_test_pos,
    }


def build_train_manifest(
    source: Path,
    shuffled: Path,
    graph_source: Path,
    graph: str,
    checkpoint_dir: Path,
    test_set: Path | None,
    out: Path,
) -> dict:
    params = effective_parameters(graph)
    wdl = params["wdl"]
    manifest = {
        "schema_version": 2,
        "kind": "bullet_train",
        "dataset": {
            "path": str(source.resolve()),
            "sha256": sha256_file(source),
            "bytes": source.stat().st_size,
        },
        "shuffled": {
            "path": str(shuffled.resolve()),
            "sha256": sha256_file(shuffled) if shuffled.is_file() else None,
            "bytes": shuffled.stat().st_size if shuffled.is_file() else None,
        },
        "graph": {
            "name": graph,
            "source": str(graph_source.resolve()),
            "sha256": sha256_file(graph_source),
            "graph_id": expected_graph_id(graph, wdl),
        },
        "checkpoint_dir": str(checkpoint_dir),
        "validation": {
            "path": str(test_set.resolve()) if test_set is not None else None,
            "sha256": sha256_file(test_set) if test_set is not None and test_set.is_file() else None,
            "game_relation": game_relation(source, test_set)
            if test_set is not None and test_set.is_file()
            else None,
        },
        "parameters": params,
    }
    write_manifest(out, manifest)
    return manifest


def _cmd_reuse_ok(args: argparse.Namespace) -> int:
    source = Path(args.source)
    shuffled = Path(args.shuffled)
    sidecar = read_sidecar(Path(args.sidecar))
    decision = shuffle_decision(
        sha256_file(source),
        source.stat().st_size,
        shuffled.stat().st_size if shuffled.is_file() else None,
        None if sidecar is None else str(sidecar.get("source_sha256")),
        True,
    )
    print(decision)
    return 0 if decision == "reuse" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    reuse = sub.add_parser("reuse-ok")
    reuse.add_argument("--source", required=True)
    reuse.add_argument("--shuffled", required=True)
    reuse.add_argument("--sidecar", required=True)

    write = sub.add_parser("write-sidecar")
    write.add_argument("--source", required=True)
    write.add_argument("--sidecar", required=True)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--source", required=True)
    manifest.add_argument("--shuffled", required=True)
    manifest.add_argument("--graph-source", required=True)
    manifest.add_argument("--graph", required=True)
    manifest.add_argument("--checkpoint-dir", required=True)
    manifest.add_argument("--test-set", default="")
    manifest.add_argument("--out", required=True)

    games = sub.add_parser("games")
    games.add_argument("--train", required=True)
    games.add_argument("--test", required=True)

    split = sub.add_parser("split")
    split.add_argument("--source", required=True)
    split.add_argument("--train", required=True)
    split.add_argument("--test", required=True)
    split.add_argument("--fraction", type=float, default=0.05)
    split.add_argument("--seed", type=int, default=1)

    args = parser.parse_args()
    if args.cmd == "reuse-ok":
        return _cmd_reuse_ok(args)
    if args.cmd == "write-sidecar":
        print(write_sidecar(Path(args.source), Path(args.sidecar))["source_sha256"])
        return 0
    if args.cmd == "manifest":
        test = Path(args.test_set) if args.test_set else None
        build_train_manifest(
            Path(args.source),
            Path(args.shuffled),
            Path(args.graph_source),
            args.graph,
            Path(args.checkpoint_dir),
            test,
            Path(args.out),
        )
        print(args.out)
        return 0
    if args.cmd == "games":
        relation = game_relation(Path(args.train), Path(args.test))
        print(relation)
        return 0 if relation == "disjoint" else 1
    if args.cmd == "split":
        summary = split_games(
            Path(args.source), Path(args.train), Path(args.test), args.fraction, args.seed
        )
        print(json.dumps(summary))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
