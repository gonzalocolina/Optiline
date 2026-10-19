#!/usr/bin/env python3
"""Train the HL graph (768→512)×2 SCReLU → 32 SCReLU → 1 on a bulletformat file.

SCReLU has no slope outside (0, 1). `--window` adds a training penalty, zero
inside that interval, that pulls a preactivation back in. The engine still
evaluates plain SCReLU. With that penalty the wide FT stays inside (0, 1) at
learning rate 0.001; without it, that rate pushes units out of the interval.

bullet's current trainer only runs on CUDA or ROCm. This is the same graph,
init, AdamW and quantised layout, on CPU, for a machine without a GPU.
NSCE_WDL is 0, so the result byte is unused. The objective is Huber on
cp/400, not squared error of sigmoid(cp/400): on this width the probability
loss goes flat while centipawn error is still large.
"""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from jsonl_to_bullet import RECORD  # noqa: E402

FT = 512
HL = 32
FEATURES = 768
QA = 255
QB = 64
SCALE = 400.0
# Huber switches from quadratic to linear past this centipawn error.
CP_DELTA = 600.0
RECORD_SIZE = 32


def decode_records(blob: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return stm features, ntm features (N, 32) int16 with -1 padding, and white-relative cp."""
    if len(blob) % RECORD_SIZE != 0:
        raise ValueError(f"bullet file is {len(blob)} bytes")
    n = len(blob) // RECORD_SIZE
    stm = np.full((n, 32), -1, np.int16)
    ntm = np.full((n, 32), -1, np.int16)
    scores = np.empty(n, np.float32)
    for i in range(n):
        raw = blob[i * RECORD_SIZE : (i + 1) * RECORD_SIZE]
        occ, pcs, score, _result, _ksq, _opp, _a, _b, _c = RECORD.unpack(raw)
        scores[i] = score
        remaining = occ
        slot = 0
        while remaining:
            sq = (remaining & -remaining).bit_length() - 1
            remaining &= remaining - 1
            nibble = (pcs[slot // 2] >> (4 * (slot & 1))) & 0x0F
            colour = (nibble >> 3) & 1
            piece = nibble & 7
            base = 64 * piece + sq
            stm[i, slot] = (384 if colour else 0) + base
            ntm[i, slot] = (0 if colour else 384) + 64 * piece + (sq ^ 56)
            slot += 1
            if slot > 32:
                raise ValueError(f"record {i} has more than 32 pieces")
    return stm, ntm, scores


def init_params(rng: np.random.Generator) -> dict[str, np.ndarray]:
    l0_std = np.sqrt(2.0 / FEATURES).astype(np.float32)
    l1_std = (np.sqrt(2.0 / (2 * FT)) / 4.0).astype(np.float32)
    l2_std = np.sqrt(2.0 / HL).astype(np.float32)
    return {
        "l0w": rng.normal(0.0, l0_std, size=(FEATURES, FT)).astype(np.float32),
        "l0b": rng.normal(0.15, 0.02, size=(FT,)).astype(np.float32),
        "l1w": rng.normal(0.0, l1_std, size=(HL, 2 * FT)).astype(np.float32),
        "l1b": rng.normal(0.4, 0.05, size=(HL,)).astype(np.float32),
        "l2w": rng.normal(0.0, l2_std, size=(HL,)).astype(np.float32),
        "l2b": np.zeros(1, np.float32),
    }


def _accumulate(idx: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
    acc = np.broadcast_to(bias, (idx.shape[0], bias.shape[0])).copy()
    for slot in range(idx.shape[1]):
        col = idx[:, slot]
        mask = col >= 0
        acc[mask] += weight[col[mask]]
    return acc


_SCATTER = None


def _scatter_lib():
    global _SCATTER
    if _SCATTER is not None:
        return _SCATTER
    src = r"""
#include <stdint.h>
void hl_scatter(const int16_t* idx, const float* grad, float* out,
                 int batch, int slots, int hidden, int features) {
  (void)features;
  for (int b = 0; b < batch; ++b) {
    const float* g = grad + b * hidden;
    const int16_t* row = idx + b * slots;
    for (int k = 0; k < slots; ++k) {
      int feature = row[k];
      if (feature < 0) continue;
      float* dst = out + feature * hidden;
      for (int h = 0; h < hidden; ++h) dst[h] += g[h];
    }
  }
}
"""
    path = Path("/tmp/nsce_hl_scatter.c")
    lib = Path("/tmp/nsce_hl_scatter.so")
    path.write_text(src)
    subprocess.check_call(["gcc", "-O3", "-fPIC", "-shared", "-o", str(lib), str(path)])
    loaded = ctypes.CDLL(str(lib))
    loaded.hl_scatter.argtypes = [
        ctypes.POINTER(ctypes.c_int16),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    _SCATTER = loaded
    return loaded


def _scatter(idx: np.ndarray, grad: np.ndarray, out: np.ndarray) -> None:
    idx = np.ascontiguousarray(idx, dtype=np.int16)
    grad = np.ascontiguousarray(grad, dtype=np.float32)
    lib = _scatter_lib()
    lib.hl_scatter(
        idx.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
        grad.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        idx.shape[0],
        idx.shape[1],
        grad.shape[1],
        out.shape[0],
    )


def screlu(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    clipped = np.clip(x, 0.0, 1.0)
    return clipped * clipped, clipped


def forward(params: dict[str, np.ndarray], stm: np.ndarray, ntm: np.ndarray) -> dict[str, np.ndarray]:
    stm_pre = _accumulate(stm, params["l0w"], params["l0b"])
    ntm_pre = _accumulate(ntm, params["l0w"], params["l0b"])
    stm_act, stm_clamped = screlu(stm_pre)
    ntm_act, ntm_clamped = screlu(ntm_pre)
    hidden_in = np.concatenate((stm_act, ntm_act), axis=1)
    h_pre = hidden_in @ params["l1w"].T + params["l1b"]
    h_act, h_clamped = screlu(h_pre)
    logit = h_act @ params["l2w"] + params["l2b"]
    return {
        "stm_pre": stm_pre,
        "ntm_pre": ntm_pre,
        "stm_clamped": stm_clamped,
        "ntm_clamped": ntm_clamped,
        "hidden_in": hidden_in,
        "h_pre": h_pre,
        "h_act": h_act,
        "h_clamped": h_clamped,
        "logit": logit,
    }


def window_pull(pre: np.ndarray, coeff: float) -> np.ndarray:
    """Gradient of a penalty that is zero inside (0, 1) and quadratic outside.

    SCReLU itself has slope zero outside that interval, so a unit that leaves
    never receives a task gradient. This term pulls it back. It is not part of
    the evaluated network.
    """
    if coeff == 0.0:
        return np.zeros_like(pre)
    outside = np.where(pre < 0.0, pre, np.where(pre > 1.0, pre - 1.0, 0.0))
    return np.asarray(2.0 * coeff / pre.shape[0] * outside, dtype=np.float32)


def occupancy(params: dict[str, np.ndarray], stm: np.ndarray, ntm: np.ndarray) -> tuple[float, int, float]:
    cache = forward(params, stm, ntm)
    ft = np.concatenate((cache["stm_pre"], cache["ntm_pre"]), axis=0)
    inside = (ft > 0.0) & (ft < 1.0)
    live = int((inside.mean(axis=0) > 0.5).sum())
    hidden = cache["h_pre"]
    hidden_inside = float(((hidden > 0.0) & (hidden < 1.0)).mean())
    return float(inside.mean()), live, hidden_inside


def loss_and_grads(
    params: dict[str, np.ndarray],
    stm: np.ndarray,
    ntm: np.ndarray,
    scores: np.ndarray,
    window: float = 0.0,
) -> tuple[float, dict[str, np.ndarray]]:
    cache = forward(params, stm, ntm)
    logit = cache["logit"].reshape(-1)
    # Squared error on sigmoid(cp/400) flattens once the wide net matches
    # probabilities: a 100 cp miss near zero is a tiny probability error, and
    # the gradient vanishes in the tails. Huber on the logit keeps a slope
    # until the centipawn error itself is small. Export is still logit * 400.
    err = logit - scores / SCALE
    delta = CP_DELTA / SCALE
    abs_err = np.abs(err)
    quadratic = abs_err <= delta
    loss = float(
        np.mean(np.where(quadratic, 0.5 * err * err, delta * (abs_err - 0.5 * delta)))
    )
    batch = logit.shape[0]
    dlogit = np.where(quadratic, err, delta * np.sign(err)).astype(np.float32) / batch

    grads = {name: np.zeros_like(value) for name, value in params.items()}
    grads["l2b"][0] = dlogit.sum()
    grads["l2w"] = cache["h_act"].T @ dlogit
    dh = dlogit[:, None] * params["l2w"]
    dh_pre = dh * (2.0 * cache["h_clamped"])
    dh_pre[(cache["h_pre"] <= 0.0) | (cache["h_pre"] >= 1.0)] = 0.0
    dh_pre += window_pull(cache["h_pre"], window)
    grads["l1b"] = dh_pre.sum(axis=0)
    grads["l1w"] = dh_pre.T @ cache["hidden_in"]
    d_hidden = dh_pre @ params["l1w"]
    d_stm = d_hidden[:, :FT] * (2.0 * cache["stm_clamped"])
    d_ntm = d_hidden[:, FT:] * (2.0 * cache["ntm_clamped"])
    d_stm[(cache["stm_pre"] <= 0.0) | (cache["stm_pre"] >= 1.0)] = 0.0
    d_ntm[(cache["ntm_pre"] <= 0.0) | (cache["ntm_pre"] >= 1.0)] = 0.0
    d_stm += window_pull(cache["stm_pre"], window)
    d_ntm += window_pull(cache["ntm_pre"], window)
    _scatter(stm, d_stm, grads["l0w"])
    _scatter(ntm, d_ntm, grads["l0w"])
    grads["l0b"] = d_stm.sum(axis=0) + d_ntm.sum(axis=0)
    return loss, grads


def adamw_step(
    params: dict[str, np.ndarray],
    grads: dict[str, np.ndarray],
    moments: dict[str, np.ndarray],
    velocity: dict[str, np.ndarray],
    lr: float,
    decay: float = 0.01,
    beta1: float = 0.9,
    beta2: float = 0.999,
) -> None:
    for name in params:
        weight = params[name]
        grad = grads[name]
        weight *= 1.0 - decay * lr
        moments[name] = beta1 * moments[name] + (1.0 - beta1) * grad
        velocity[name] = beta2 * velocity[name] + (1.0 - beta2) * grad * grad
        weight -= lr * moments[name] / (np.sqrt(velocity[name]) + 1e-8)
        np.clip(weight, -1.98, 1.98, out=weight)


def quantise(params: dict[str, np.ndarray]) -> bytes:
    """bullet HL quantised.bin: l0 plain, l1w as [32][1024], biases at their factors."""

    def q_i16(values: np.ndarray, factor: float) -> bytes:
        rounded = np.rint(values.astype(np.float64) * factor)
        clipped = np.clip(rounded, -32767, 32767).astype(np.int16)
        return clipped.tobytes()

    # l0w is stored feature-major, which is this array's C order.
    l1w = params["l1w"].reshape(HL, 2 * FT)
    return b"".join(
        (
            q_i16(params["l0w"], QA),
            q_i16(params["l0b"], QA),
            q_i16(l1w, QB),
            q_i16(params["l1b"], QA * QB),
            q_i16(params["l2w"], QB),
            q_i16(params["l2b"], QA * QB),
        )
    )


def load_params(path: Path) -> dict[str, np.ndarray]:
    stored = np.load(path)
    return {name: np.asarray(stored[name], dtype=np.float32) for name in ("l0w", "l0b", "l1w", "l1b", "l2w", "l2b")}


def band_correlation(pred: np.ndarray, scores: np.ndarray, limit: float) -> tuple[float, float, int]:
    mask = np.abs(scores) < limit
    if int(mask.sum()) < 20:
        return float("nan"), float("nan"), int(mask.sum())
    picked_pred = pred[mask]
    picked_scores = scores[mask]
    centered_pred = picked_pred - picked_pred.mean()
    centered_scores = picked_scores - picked_scores.mean()
    denom = float(np.sqrt((centered_pred ** 2).sum() * (centered_scores ** 2).sum()))
    corr = float((centered_pred * centered_scores).sum() / denom) if denom else float("nan")
    mae = float(np.mean(np.abs(picked_pred - picked_scores)))
    return corr, mae, int(mask.sum())


def train(
    path: Path,
    epochs: int,
    batch: int,
    lr: float,
    seed: int,
    out_dir: Path,
    window: float,
    init: Path | None = None,
    holdout: Path | None = None,
    patience: int = 0,
) -> Path:
    blob = path.read_bytes()
    print(f"decoding {len(blob) // RECORD_SIZE} records", flush=True)
    stm, ntm, scores = decode_records(blob)
    n = stm.shape[0]
    rng = np.random.default_rng(seed)
    params = load_params(init) if init is not None else init_params(rng)
    if init is not None:
        print(f"resume weights {init}", flush=True)
    moments = {name: np.zeros_like(value) for name, value in params.items()}
    velocity = {name: np.zeros_like(value) for name, value in params.items()}
    out_dir.mkdir(parents=True, exist_ok=True)
    hold_stm = hold_ntm = hold_scores = None
    if holdout is not None:
        import json

        rows = [json.loads(line) for line in holdout.read_text().splitlines() if line.strip()]
        from jsonl_to_bullet import fen_to_record

        packed = b"".join(fen_to_record(row["fen"], int(row["score_cp"])) for row in rows)
        hold_stm, hold_ntm, hold_scores = decode_records(packed)
        print(f"holdout {len(hold_scores)}", flush=True)
    order = np.arange(n)
    steps = n // batch
    best_quiet = -1.0
    stale = 0
    best_epoch = 0
    for epoch in range(1, epochs + 1):
        rng.shuffle(order)
        total = 0.0
        seen = 0
        for step in range(steps):
            pick = order[step * batch : (step + 1) * batch]
            loss, grads = loss_and_grads(params, stm[pick], ntm[pick], scores[pick], window)
            adamw_step(params, grads, moments, velocity, lr)
            total += loss * batch
            seen += batch
        cp = forward(params, stm[:4096], ntm[:4096])["logit"].reshape(-1) * SCALE
        mae = float(np.mean(np.abs(cp - scores[:4096])))
        ft_inside, live, hidden_inside = occupancy(params, stm[:2048], ntm[:2048])
        quiet = ""
        quiet_corr = float("nan")
        if hold_stm is not None:
            pred = forward(params, hold_stm, hold_ntm)["logit"].reshape(-1) * SCALE
            quiet_corr, quiet_mae, quiet_n = band_correlation(pred, hold_scores, 200.0)
            all_corr, all_mae, _ = band_correlation(pred, hold_scores, 1.0e9)
            quiet = (
                f" hold_corr {all_corr:.3f} hold_mae {all_mae:.1f}"
                f" quiet_corr {quiet_corr:.3f} quiet_mae {quiet_mae:.1f} n {quiet_n}"
            )
        print(
            f"epoch {epoch} loss {total / seen:.6f} mae_cp {mae:.1f} "
            f"ft_inside {ft_inside:.3f} ft_live {live}/{FT} hl_inside {hidden_inside:.3f}{quiet}",
            flush=True,
        )
        np.savez(out_dir / "latest.npz", epoch=epoch, **params)
        quantised = quantise(params)
        (out_dir / "quantised.bin").write_bytes(quantised)
        if quiet_corr > best_quiet:
            best_quiet = quiet_corr
            best_epoch = epoch
            stale = 0
            np.savez(out_dir / "best.npz", epoch=epoch, **params)
            (out_dir / "quantised_best.bin").write_bytes(quantised)
            print(f"best quiet_corr {best_quiet:.3f} at epoch {epoch}", flush=True)
        else:
            stale += 1
            if patience and stale >= patience:
                print(f"stop: quiet_corr unchanged for {patience} epochs (best {best_quiet:.3f} at {best_epoch})", flush=True)
                break
    quant_path = out_dir / "quantised_best.bin"
    if not quant_path.exists():
        quant_path = out_dir / "quantised.bin"
    print(f"wrote {quant_path} ({quant_path.stat().st_size} bytes)", flush=True)
    return quant_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "train/data/lichess_eval_2m.bin")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument(
        "--window",
        type=float,
        default=0.05,
        help="pull SCReLU preactivations back into (0, 1); 0 disables it",
    )
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--init", type=Path, default=None, help="resume float weights from this npz")
    parser.add_argument("--holdout", type=Path, default=None)
    parser.add_argument("--patience", type=int, default=0, help="stop after this many epochs without a better |cp|<200 correlation")
    parser.add_argument("--out", type=Path, default=ROOT / "train/bullet_checkpoints_hl_lichess")
    args = parser.parse_args()
    train(
        args.data,
        args.epochs,
        args.batch,
        args.lr,
        args.seed,
        args.out,
        args.window,
        args.init,
        args.holdout,
        args.patience,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
