#!/usr/bin/env python3
"""Concurrent full-length matches through fastchess.

The legacy runners (`ablation_match.py`, `sprt.py`) play one game at a time and
truncate at `--max-plies 60`, scoring the truncated game as a draw. 90% of the
equal-node gate games ended that way, so they could only resolve effects that
mate or reach ±800 cp within 30 moves. This wrapper plays games to a result
(resign / draw adjudication / rules), uses every core, and reports pentanomial
SPRT / Elo from fastchess.

Examples
--------
Equal-time gate, 1000 game pairs at 8s+0.08s, 14 concurrent games:

    python3 tools/fastchess_match.py --cfg-a tools/configs/baseline.uci \
        --cfg-b tools/configs/candidate.uci --tc 8+0.08 --rounds 1000 \
        --outdir experiments/$(date +%Y%m%d)_candidate_tc

SPRT [0, 5] nElo, stop when decided:

    python3 tools/fastchess_match.py ... --sprt 0 5 --rounds 20000

Against pinned Stockfish (no strength limit):

    python3 tools/fastchess_match.py --cfg-a tools/configs/baseline.uci \
        --engine-b third_party/stockfish/stockfish-19 --cfg-b tools/configs/sf19_unlimited.uci \
        --name-b sf19 --tc 8+0.08 --rounds 100
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import attach_frozen_targets, build_manifest, config_options, sha256_file, write_manifest  # noqa: E402

FASTCHESS = ROOT / "third_party" / "fastchess" / "fastchess"


def engine_args(name: str, cmd: Path, cfg: Path, tc: str, st_ms: int, nodes: int, cwd: Path) -> list[str]:
    args = ["-engine", f"cmd={cmd.resolve()}", f"name={name}", f"dir={cwd}"]
    if nodes > 0:
        args.append(f"nodes={nodes}")
        args.append("tc=inf")
    elif st_ms > 0:
        args.append(f"st={st_ms / 1000.0:g}")
        args.append("timemargin=200")
    else:
        args.append(f"tc={tc}")
        args.append("timemargin=100")
    for option, value in config_options(ROOT, [cfg]).items():
        args.append(f"option.{option}={value}")
    return args


SUMMARY_RE = re.compile(r"^(Results of|Elo|nElo|LOS|Games|Ptnml|LLR|SPRT|Penta)", re.MULTILINE)


def parse_summary(text: str) -> dict:
    """Pull the final fastchess result block into a dict."""
    out: dict = {}
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("Results of"):
            m = re.search(r"Results of (\S+) vs (\S+)", line)
            if m:
                out["name_a"], out["name_b"] = m.group(1), m.group(2)
        elif line.startswith("Elo:"):
            m = re.search(r"Elo:\s*([-+]?\d+\.?\d*)\s*\+/-\s*(\d+\.?\d*)", line)
            if m:
                out["elo_a_minus_b"] = float(m.group(1))
                out["elo_err_95"] = float(m.group(2))
            m = re.search(r"nElo:\s*([-+]?\d+\.?\d*)\s*\+/-\s*(\d+\.?\d*)", line)
            if m:
                out["nelo"] = float(m.group(1))
                out["nelo_err_95"] = float(m.group(2))
        elif line.startswith("LOS:"):
            m = re.search(r"LOS:\s*(\d+\.?\d*)\s*%.*DrawRatio:\s*(\d+\.?\d*)\s*%", line)
            if m:
                out["los_pct"] = float(m.group(1))
                out["draw_ratio_pct"] = float(m.group(2))
        elif line.startswith("Games:"):
            m = re.search(r"Games:\s*(\d+),\s*Wins:\s*(\d+),\s*Losses:\s*(\d+),\s*Draws:\s*(\d+)", line)
            if m:
                out["games"] = int(m.group(1))
                out["W"] = int(m.group(2))
                out["L"] = int(m.group(3))
                out["D"] = int(m.group(4))
            m = re.search(r"Points:\s*([\d.]+)\s*\(([\d.]+)\s*%\)", line)
            if m:
                out["points"] = float(m.group(1))
                out["score_pct"] = float(m.group(2))
        elif line.startswith("Ptnml"):
            m = re.search(r"\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]", line)
            if m:
                out["pentanomial"] = [int(m.group(i)) for i in range(1, 6)]
        elif line.startswith("LLR:"):
            m = re.search(r"LLR:\s*([-+]?\d+\.?\d*)\s*\(([-+]?\d+\.?\d*),\s*([-+]?\d+\.?\d*)\)\s*(.*)$", line)
            if m:
                out["llr"] = float(m.group(1))
                out["llr_bounds"] = [float(m.group(2)), float(m.group(3))]
                out["sprt_hypothesis"] = m.group(4).strip()
    if "sprt_hypothesis" in out:
        h = out["sprt_hypothesis"]
        out["sprt_decision"] = "H1" if "H1" in h else "H0" if "H0" in h else "inconclusive"
        out["decision"] = {
            "H1": "accept_H1_candidate_stronger",
            "H0": "accept_H0_baseline_not_weaker",
        }.get(out["sprt_decision"], "inconclusive")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fastchess", default=str(FASTCHESS))
    ap.add_argument("--engine", default=str(ROOT / "build" / "nsce"))
    ap.add_argument("--engine-b", default="", help="second binary (default: same as --engine)")
    ap.add_argument("--cfg-a", default=str(ROOT / "tools/configs/baseline.uci"))
    ap.add_argument("--cfg-b", required=True)
    ap.add_argument("--name-a", default="baseline")
    ap.add_argument("--name-b", default="candidate")
    ap.add_argument("--tc", default="8+0.08", help="cutechess-style time control, e.g. 8+0.08 or 40/60")
    ap.add_argument("--st", type=int, default=0, help="fixed movetime in ms (overrides --tc)")
    ap.add_argument("--nodes", type=int, default=0, help="fixed nodes per move (overrides --tc/--st)")
    ap.add_argument("--rounds", type=int, default=250, help="opening pairs (games = 2 * rounds)")
    ap.add_argument("--concurrency", type=int, default=14)
    ap.add_argument("--sprt", nargs=2, type=float, metavar=("ELO0", "ELO1"), default=None)
    ap.add_argument("--sprt-model", choices=("normalized", "logistic"), default="normalized")
    ap.add_argument("--openings", default=str(ROOT / "tools/openings_uho.epd"))
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--maxmoves", type=int, default=300)
    ap.add_argument("--resign-score", type=int, default=1000)
    ap.add_argument("--resign-movecount", type=int, default=4)
    ap.add_argument("--draw-movenumber", type=int, default=40)
    ap.add_argument("--draw-movecount", type=int, default=8)
    ap.add_argument("--draw-score", type=int, default=10)
    ap.add_argument("--no-adjudication", action="store_true")
    ap.add_argument("--outdir", default="")
    ap.add_argument(
        "--frozen-targets",
        default=str(ROOT / "experiments/frozen-targets/manifest.json"),
    )
    args = ap.parse_args()

    fastchess = Path(args.fastchess)
    if not fastchess.exists():
        print(f"fastchess not found at {fastchess}; build it: git clone https://github.com/Disservin/fastchess "
              f"third_party/fastchess && make -C third_party/fastchess -j", file=sys.stderr)
        return 1
    engine_a = Path(args.engine)
    engine_b = Path(args.engine_b) if args.engine_b else engine_a
    cfg_a, cfg_b = Path(args.cfg_a), Path(args.cfg_b)
    for p in (engine_a, engine_b, cfg_a, cfg_b):
        if not p.exists():
            print(f"missing: {p}", file=sys.stderr)
            return 1

    outdir = Path(args.outdir) if args.outdir else ROOT / "experiments" / f"{date.today():%Y%m%d}_fastchess"
    outdir.mkdir(parents=True, exist_ok=True)
    pgn = outdir / f"games_{args.name_a}_vs_{args.name_b}.pgn"
    log = outdir / "fastchess.log"

    cmd = [str(fastchess)]
    cmd += engine_args(args.name_a, engine_a, cfg_a, args.tc, args.st, args.nodes, ROOT)
    cmd += engine_args(args.name_b, engine_b, cfg_b, args.tc, args.st, args.nodes, ROOT)
    cmd += ["-each", "proto=uci"]
    cmd += ["-rounds", str(args.rounds), "-games", "2", "-repeat", "-recover"]
    cmd += ["-concurrency", str(args.concurrency)]
    cmd += ["-openings", f"file={Path(args.openings).resolve()}", "format=epd", "order=random"]
    cmd += ["-srand", str(args.seed)]
    cmd += ["-maxmoves", str(args.maxmoves)]
    if not args.no_adjudication:
        cmd += ["-resign", f"movecount={args.resign_movecount}", f"score={args.resign_score}", "twosided=true"]
        cmd += ["-draw", f"movenumber={args.draw_movenumber}", f"movecount={args.draw_movecount}",
                f"score={args.draw_score}"]
    if args.sprt is not None:
        cmd += ["-sprt", f"elo0={args.sprt[0]:g}", f"elo1={args.sprt[1]:g}", "alpha=0.05", "beta=0.05",
                f"model={args.sprt_model}"]
    cmd += ["-ratinginterval", "20", "-report", "penta=true"]
    cmd += ["-pgnout", f"file={pgn}", "nodes=true", "nps=true", "min=true"]
    cmd += ["-log", f"file={log}", "level=warn", "realtime=false"]

    (outdir / "command.txt").write_text(" ".join(cmd) + "\n")
    print(" ".join(cmd), flush=True)

    captured: list[str] = []
    with subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            captured.append(line)
        rc = proc.wait()
    text = "".join(captured)
    (outdir / "fastchess_stdout.txt").write_text(text)

    # fastchess prints a results block every ratinginterval; keep the last one.
    blocks = text.split("--------------------------------------------------")
    final = ""
    for block in reversed(blocks):
        if "Results of" in block:
            final = block
            break
    summary = parse_summary(final or text)
    summary.update(
        {
            "engine_a": str(engine_a.resolve()),
            "engine_b": str(engine_b.resolve()),
            "cfg_a": str(cfg_a),
            "cfg_b": str(cfg_b),
            "harness": "fastchess",
            "tc": args.tc if not args.st and not args.nodes else None,
            "st_ms": args.st or None,
            "movetime_ms": args.st or 0,
            "nodes_per_move": args.nodes or None,
            "rounds": args.rounds,
            "concurrency": args.concurrency,
            "seed": args.seed,
            "sprt": args.sprt,
            "adjudication": None
            if args.no_adjudication
            else {
                "resign_score": args.resign_score,
                "resign_movecount": args.resign_movecount,
                "draw_movenumber": args.draw_movenumber,
                "draw_movecount": args.draw_movecount,
                "draw_score": args.draw_score,
                "maxmoves": args.maxmoves,
            },
            "fastchess_exit_code": rc,
            "pgn": str(pgn),
        }
    )
    (outdir / f"match_{args.name_a}_vs_{args.name_b}.json").write_text(json.dumps(summary, indent=2))

    limit = f"{args.nodes} nodes/move" if args.nodes else f"{args.st} ms/move" if args.st else f"tc {args.tc}"
    lines = [
        f"# fastchess match — {outdir.name}",
        "",
        f"- A: `{args.name_a}` = `{engine_a}` + `{cfg_a}`",
        f"- B: `{args.name_b}` = `{engine_b}` + `{cfg_b}`",
        f"- Limit: {limit}; concurrency {args.concurrency}; openings `{Path(args.openings).name}` random seed {args.seed}",
        "- Games play to a result (resign ±{}cp × {}, draw after move {} |cp|<{} × {}, max {} moves)".format(
            args.resign_score, args.resign_movecount, args.draw_movenumber, args.draw_score,
            args.draw_movecount, args.maxmoves) if not args.no_adjudication else "- No adjudication",
        f"- Date: {date.today().isoformat()}",
        "",
        "## Result (A − B)",
        "",
        "```text",
        (final or text).strip(),
        "```",
        "",
    ]
    if "elo_a_minus_b" in summary:
        lines.append(
            f"**{summary.get('W')}-{summary.get('D')}-{summary.get('L')}**, N={summary.get('games')}, "
            f"Elo A−B **{summary['elo_a_minus_b']:+.1f} ± {summary['elo_err_95']:.1f}**, "
            f"nElo {summary.get('nelo', float('nan')):+.1f} ± {summary.get('nelo_err_95', float('nan')):.1f}, "
            f"draw ratio {summary.get('draw_ratio_pct', float('nan')):.1f}%, "
            f"pentanomial {summary.get('pentanomial')}"
            + (f", SPRT LLR {summary['llr']:+.2f} → **{summary['sprt_decision']}**" if "llr" in summary else "")
        )
    (outdir / "report.md").write_text("\n".join(lines) + "\n")

    manifest = attach_frozen_targets(
        build_manifest(
            ROOT,
            engine_a,
            [cfg_a, cfg_b],
            Path(args.openings),
            args.seed,
            {
                "kind": "fastchess_match",
                "harness": "fastchess",
                "harness_sha256": sha256_file(fastchess),
                "tc": args.tc,
                "st_ms": args.st,
                "nodes_per_move": args.nodes,
                "rounds": args.rounds,
                "concurrency": args.concurrency,
                "sprt": args.sprt,
                "engine_b": str(engine_b.resolve()),
                "engine_b_sha256": sha256_file(engine_b),
                "full_length_games": True,
                "state_isolation": "normal_game_warm",
            },
        ),
        Path(args.frozen_targets) if args.frozen_targets else None,
    )
    write_manifest(outdir / "manifest.json", manifest)
    print(f"\nwrote {outdir}/report.md")
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
