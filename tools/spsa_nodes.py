#!/usr/bin/env python3
"""SPSA over the engine's tune spins at a fixed node count per move.

Fixed nodes make the result independent of machine load, so the tuner can share
a host with training or other matches. W workers run in parallel. Each one
perturbs every listed constant by +/- c_k, plays P game pairs theta+ against
theta- through fastchess on one core, and applies the Fishtest update

    theta += r_k * c_k * (wins - losses) * delta

with the schedule counted in game pairs. The state is written after every
update to OUT/state.json, and a run restarted with the same OUT resumes from it.

The engine must be built with -DNSCE_TUNE=ON so that it advertises the spins.

Example
-------
    cmake -S . -B build-tune -DNSCE_TUNE=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build build-tune -j --target nsce
    python3 tools/spsa_nodes.py --engine build-tune/nsce \
        --eval-file nets/nsceper1_hl_full.bin --use-extras false \
        --total-pairs 14000 --nodes 32000 --out experiments/$(date +%Y%m%d)_spsa
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALPHA = 0.602
GAMMA = 0.101


def advertised_spins(engine: Path) -> dict[str, dict[str, float]]:
    out = subprocess.run([str(engine)], input="uci\nquit\n", capture_output=True, text=True, cwd=ROOT).stdout
    spins = {}
    for line in out.splitlines():
        m = re.match(r"option name (\S+) type spin default (-?\d+) min (-?\d+) max (-?\d+)", line)
        if m:
            spins[m.group(1)] = {"value": float(m.group(2)), "lo": int(m.group(3)), "hi": int(m.group(4))}
    return spins


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", required=True, help="nsce built with -DNSCE_TUNE=ON")
    ap.add_argument("--fastchess", default=str(ROOT / "third_party/fastchess/fastchess"))
    ap.add_argument("--openings", default=str(ROOT / "tools/openings_uho.epd"))
    ap.add_argument("--eval-file", default="nets/nsceper1_hl_full.bin")
    ap.add_argument("--use-extras", default="false")
    ap.add_argument("--steps", default=str(ROOT / "tools/configs/spsa_nodes_steps.json"),
                    help="JSON map from spin name to its final perturbation c_end; only these spins are tuned")
    ap.add_argument("--total-pairs", type=int, default=14000)
    ap.add_argument("--pairs", type=int, default=2, help="game pairs per perturbation")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--nodes", type=int, default=32000)
    ap.add_argument("--r-end", type=float, default=0.003)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    engine = Path(args.engine).resolve()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    steps = json.loads(Path(args.steps).read_text())
    spins = advertised_spins(engine)
    missing = sorted(set(steps) - set(spins))
    if missing:
        print(f"{engine} does not advertise: {', '.join(missing)}. Build it with -DNSCE_TUNE=ON.", file=sys.stderr)
        return 1
    params = {name: spins[name] for name in sorted(steps)}

    state_path = out / "state.json"
    done = 0
    if state_path.exists():
        saved = json.loads(state_path.read_text())
        done = saved["pairs"]
        for name, value in saved["theta"].items():
            if name in params:
                params[name]["value"] = value

    total = args.total_pairs
    stability = 0.1 * total
    for name, p in params.items():
        c_end = float(steps[name])
        p["c"] = c_end * total**GAMMA
        p["a"] = args.r_end * c_end**2 * (stability + total) ** ALPHA

    lock = threading.Lock()
    log = (out / "log.txt").open("a")
    state = {"done": done, "started": done, "seq": 0}

    def clamp(p: dict[str, float], value: float) -> float:
        return min(p["hi"], max(p["lo"], value))

    def worker(wid: int) -> None:
        rng = random.Random(args.seed * 7919 + wid * 104729 + done)
        wdir = out / f"w{wid}"
        wdir.mkdir(exist_ok=True)
        while True:
            with lock:
                if state["started"] >= total:
                    return
                state["started"] += args.pairs
                state["seq"] += 1
                seq = state["seq"]
                k = max(1, state["done"] + args.pairs)
                ck = {n: p["c"] / k**GAMMA for n, p in params.items()}
                delta = {n: rng.choice((-1, 1)) for n in params}
                plus = {n: int(clamp(p, round(p["value"] + ck[n] * delta[n]))) for n, p in params.items()}
                minus = {n: int(clamp(p, round(p["value"] - ck[n] * delta[n]))) for n, p in params.items()}

            def side(name: str, values: dict[str, int]) -> list[str]:
                cmd = ["-engine", f"cmd={engine}", f"name={name}", f"dir={ROOT}", f"nodes={args.nodes}", "tc=inf",
                       "option.Hash=16", "option.Threads=1", f"option.EvalFile={args.eval_file}",
                       f"option.UseExtras={args.use_extras}"]
                return cmd + [f"option.{n}={v}" for n, v in values.items()]

            cmd = [args.fastchess] + side("plus", plus) + side("minus", minus) + [
                "-each", "proto=uci", "-rounds", str(args.pairs), "-games", "2", "-repeat", "-recover",
                "-concurrency", "1", "-openings", f"file={args.openings}", "format=epd", "order=random",
                "-srand", str(args.seed * 1000003 + seq * 31 + wid), "-maxmoves", "300",
                "-resign", "movecount=4", "score=1000", "twosided=true",
                "-draw", "movenumber=40", "movecount=8", "score=10"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=wdir)
            tallies = re.findall(r"Games:\s*(\d+),\s*Wins:\s*(\d+),\s*Losses:\s*(\d+),\s*Draws:\s*(\d+)", result.stdout)
            with lock:
                if not tallies:
                    log.write(f"worker {wid}: no result\n{result.stdout[-300:]}\n")
                    log.flush()
                    state["started"] -= args.pairs
                    continue
                _, wins, losses, _ = map(int, tallies[-1])
                state["done"] += args.pairs
                k = state["done"]
                for n, p in params.items():
                    r_k = p["a"] / (stability + k) ** ALPHA / ck[n] ** 2
                    p["value"] = clamp(p, p["value"] + r_k * ck[n] * (wins - losses) * delta[n])
                theta = {n: p["value"] for n, p in params.items()}
                tmp = state_path.with_suffix(".tmp")
                tmp.write_text(json.dumps({"pairs": k, "theta": theta}, indent=1))
                os.replace(tmp, state_path)
                if (k // args.pairs) % 25 == 0:
                    log.write(f"pairs {k} {time.strftime('%H:%M:%S')} " +
                              " ".join(f"{n}={v:.1f}" for n, v in theta.items()) + "\n")
                    log.flush()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"{state['done']} pairs; state in {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
