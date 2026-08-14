"""One-change and extras contract for evaluator candidates.

768 nets carry extras(); king-bucket nets do not. Mixing those with policy,
controller, or EvalScale in one SPRT is how the lab lost the ability to tell
what failed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

EVAL_GROUP = frozenset({"EvalFile", "UseNNUE", "UseExtras"})
POLICY_GROUP = frozenset({"UsePolicy", "PolicyFile"})
CONTROLLER_GROUP = frozenset({"UseSearchController", "ControllerFile"})
SEARCH_RETUNE_GROUP = frozenset(
    {
        "EvalScale",
        "UseTT",
        "UseSEE",
        "UseLMR",
        "UseNullMove",
        "UseFutility",
        "UseLMP",
        "UseRazoring",
        "UseRFP",
        "UseProbCut",
    }
)
IGNORED = frozenset({"Hash", "Threads", "TelemetryFile", "LeafTelemetryFile"})
GROUP_NAMES = {
    "eval": EVAL_GROUP,
    "policy": POLICY_GROUP,
    "controller": CONTROLLER_GROUP,
    "search_retune": SEARCH_RETUNE_GROUP,
}

KING_BUCKET_MAGICS = {b"NSCEHFKP", b"NSCEKAT1"}
NNUE768_MAGICS = {b"NSCENNUE"}


def parse_uci_options(path: Path) -> dict[str, str]:
    options: dict[str, str] = {}
    if not path.exists():
        return options
    for line in path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) < 5 or parts[0].lower() != "setoption" or parts[1].lower() != "name":
            continue
        try:
            value_index = parts.index("value")
        except ValueError:
            continue
        options[" ".join(parts[2:value_index])] = " ".join(parts[value_index + 1 :])
    return options


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_eval_file(root: Path, value: str) -> Path | None:
    text = (value or "").strip()
    if not text or text.lower() in {"internal", "hce", "<internal>", "<empty>"}:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = root / path
    return path


def net_kind(eval_file: str, root: Path | None = None) -> str:
    text = (eval_file or "internal").strip()
    if text.lower() in {"internal", "hce", "<internal>", ""}:
        return "nnue768"
    path = resolve_eval_file(root or ROOT, text)
    if path is None or not path.exists():
        return "unknown"
    magic = path.read_bytes()[:8]
    if magic in NNUE768_MAGICS:
        return "nnue768"
    if magic in KING_BUCKET_MAGICS:
        return "king_bucket"
    return "unknown"


def extras_required(kind: str) -> bool | None:
    if kind == "nnue768":
        return True
    if kind == "king_bucket":
        return False
    return None


def extras_contract_errors(eval_file: str, use_extras: str | bool, root: Path | None = None) -> list[str]:
    kind = net_kind(eval_file, root)
    required = extras_required(kind)
    extras_on = truthy(str(use_extras)) if not isinstance(use_extras, bool) else use_extras
    if required is None:
        return [f"cannot determine extras contract for EvalFile={eval_file!r}"]
    if required and not extras_on:
        return ["768 nets must keep UseExtras=true (load-bearing on the frozen arbiter)"]
    if not required and extras_on:
        return ["king-bucket nets must keep UseExtras=false (extras fight the net)"]
    return []


def changed_options(baseline: dict[str, str], candidate: dict[str, str]) -> dict[str, tuple[str, str]]:
    keys = (set(baseline) | set(candidate)) - IGNORED
    changed: dict[str, tuple[str, str]] = {}
    for key in sorted(keys):
        left = baseline.get(key, "")
        right = candidate.get(key, "")
        if left != right:
            changed[key] = (left, right)
    return changed


def change_groups(changed: Iterable[str]) -> list[str]:
    keys = set(changed)
    groups = [name for name, options in GROUP_NAMES.items() if keys & options]
    leftover = keys - set().union(*GROUP_NAMES.values())
    if leftover:
        groups.append("other:" + ",".join(sorted(leftover)))
    return groups


def one_change_errors(
    baseline: dict[str, str],
    candidate: dict[str, str],
    *,
    allow_search_retune: bool = False,
) -> list[str]:
    changed = changed_options(baseline, candidate)
    groups = change_groups(changed)
    errors: list[str] = []
    if not groups:
        errors.append("candidate UCI is identical to baseline; not a candidate")
        return errors
    if len(groups) != 1:
        errors.append(
            "candidate changes more than one contract group "
            f"({', '.join(groups)}): {sorted(changed)}"
        )
    group = groups[0] if len(groups) == 1 else None
    if group == "search_retune" and not allow_search_retune:
        errors.append(
            "search-margin/EvalScale retune is only legal after an eval candidate "
            "already won equal-node and equal-time"
        )
    if group == "eval":
        extras_changes = {key: value for key, value in changed.items() if key == "UseExtras"}
        eval_file = candidate.get("EvalFile", baseline.get("EvalFile", "internal"))
        use_extras = candidate.get("UseExtras", baseline.get("UseExtras", "true"))
        errors.extend(extras_contract_errors(eval_file, use_extras))
        required = extras_required(net_kind(eval_file))
        if extras_changes and required is not None:
            want = "true" if required else "false"
            if str(use_extras).lower() != want:
                errors.append(f"UseExtras changed to {use_extras!r}; contract requires {want}")
    return errors


def candidate_score_from_ablation(result: dict) -> tuple[float, int, float, float]:
    """Return (candidate_score, games, elo_a_minus_b, elo_err) assuming A is baseline."""
    games = int(result.get("games") or 0)
    wins = int(result.get("W") or 0)
    draws = int(result.get("D") or 0)
    losses = int(result.get("L") or 0)
    if games <= 0:
        games = wins + draws + losses
    candidate_score = (losses + 0.5 * draws) / games if games else 0.0
    elo = float(result.get("elo_diff_a_minus_b") or 0.0)
    err = float(result.get("elo_err_95") or 0.0)
    return candidate_score, games, elo, err


def equal_node_not_losing(result: dict, min_games: int = 200) -> list[str]:
    nodes = int(result.get("nodes_per_move") or 0)
    score, games, elo, err = candidate_score_from_ablation(result)
    errors: list[str] = []
    if nodes <= 0:
        errors.append("equal-node gate requires go-nodes (nodes_per_move > 0)")
    if games < min_games or games % 2:
        errors.append(f"equal-node has {games} games; need even N>={min_games}")
    # Baseline clearly stronger ⇒ clone/candidate lost.
    if elo - err > 0:
        errors.append(
            f"candidate loses equal-node: baseline {elo:.1f}±{err:.1f} Elo, "
            f"candidate score {score:.3f}"
        )
    return errors


def equal_node_clearly_winning(result: dict, min_games: int = 200) -> list[str]:
    errors = equal_node_not_losing(result, min_games=min_games)
    score, games, elo, err = candidate_score_from_ablation(result)
    if games >= min_games and not (score > 0.5 and elo + err < 0):
        errors.append(
            f"candidate is not clearly above 0.5 at equal nodes "
            f"(score {score:.3f}, baseline Elo {elo:.1f}±{err:.1f})"
        )
    return errors
