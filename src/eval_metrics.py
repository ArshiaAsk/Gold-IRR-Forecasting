"""
Metrics for the Stage 3 evaluation protocol (docs/EVAL_PROTOCOL.md §7).

All functions operate on aligned 1-D arrays of realised log returns and
predictions.  Nothing here knows about models, folds or files.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import binomtest, t as student_t


def _as_arrays(y, pred):
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    if y.shape != pred.shape:
        raise ValueError(f"shape mismatch: y {y.shape}, pred {pred.shape}")
    return y, pred


def rmse(y, pred) -> float:
    y, pred = _as_arrays(y, pred)
    return float(np.sqrt(np.mean((y - pred) ** 2)))


def mae(y, pred) -> float:
    y, pred = _as_arrays(y, pred)
    return float(np.mean(np.abs(y - pred)))


def r2_vs_zero(y, pred) -> float:
    """Campbell-Thompson OOS R² against the zero-return forecast."""
    y, pred = _as_arrays(y, pred)
    sse = float(np.sum((y - pred) ** 2))
    sse0 = float(np.sum(y ** 2))
    return float(1.0 - sse / sse0) if sse0 > 0 else float("nan")


def r2_vs_benchmark(y, pred, benchmark_pred) -> float:
    y, pred = _as_arrays(y, pred)
    _, bench = _as_arrays(y, benchmark_pred)
    sse = float(np.sum((y - pred) ** 2))
    sse_b = float(np.sum((y - bench) ** 2))
    return float(1.0 - sse / sse_b) if sse_b > 0 else float("nan")


def directional_accuracy(y, pred) -> dict:
    """
    Directional accuracy with a binomial test against the up-day base rate.

    The always-up predictor's accuracy is exactly the up-day base rate, so the
    test against the base rate is also the test against always-up.  A separate
    two-sided p vs 50% is returned only as a labelled supplementary value.
    """
    y, pred = _as_arrays(y, pred)
    n = len(y)
    if n == 0:
        return {k: float("nan") for k in (
            "dir_acc", "up_rate", "always_up_acc", "dir_minus_always_up",
            "binom_p_vs_baserate", "binom_p_vs_50", "dir_n",
        )}
    matches = np.sign(pred) == np.sign(y)
    acc = float(np.mean(matches))
    up_rate = float(np.mean(y > 0))
    k = int(np.sum(matches))
    p_base = binomtest(k, n, up_rate, alternative="greater").pvalue if 0 < up_rate < 1 else float("nan")
    p_50 = binomtest(k, n, 0.5, alternative="two-sided").pvalue
    return {
        "dir_acc": acc,
        "up_rate": up_rate,
        "always_up_acc": up_rate,
        "dir_minus_always_up": acc - up_rate,
        "binom_p_vs_baserate": float(p_base),
        "binom_p_vs_50": float(p_50),
        "dir_n": n,
    }


def diebold_mariano(y, pred_model, pred_benchmark, h: int = 1) -> dict:
    """
    Diebold-Mariano test on squared-error loss, Newey-West HAC variance and
    the Harvey-Leybourne-Newbold small-sample correction.

    Negative statistic => the model has lower squared error than the benchmark.
    """
    y, pm = _as_arrays(y, pred_model)
    _, pb = _as_arrays(y, pred_benchmark)
    d = (y - pm) ** 2 - (y - pb) ** 2
    n = len(d)
    if n < 3:
        return {"dm_stat": float("nan"), "dm_p_one_sided": float("nan"),
                "dm_p_two_sided": float("nan"), "dm_lag": 0, "dm_n": n}
    dbar = float(np.mean(d))
    lag = max(1, int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))
    # Newey-West long-run variance of the mean of d.
    gamma0 = float(np.mean((d - dbar) ** 2))
    lrv = gamma0
    for l in range(1, lag + 1):
        gamma = float(np.mean((d[l:] - dbar) * (d[:-l] - dbar)))
        lrv += 2.0 * (1.0 - l / (lag + 1.0)) * gamma
    var_mean = lrv / n
    if var_mean <= 0:
        return {"dm_stat": float("nan"), "dm_p_one_sided": float("nan"),
                "dm_p_two_sided": float("nan"), "dm_lag": lag, "dm_n": n}
    stat = dbar / np.sqrt(var_mean)
    # HLN correction for h-step forecasts (h=1 here).
    correction = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat_hln = float(stat * correction)
    df = n - 1
    p_two = float(2.0 * student_t.sf(abs(stat_hln), df=df))
    p_one_better = float(student_t.cdf(stat_hln, df=df))
    return {
        "dm_stat": stat_hln,
        "dm_p_one_sided": p_one_better,
        "dm_p_two_sided": p_two,
        "dm_lag": lag,
        "dm_n": n,
    }


def block_bootstrap(y, pred_model, pred_benchmark, block_len: int = 20,
                    n_boot: int = 2000, seed: int = 12345) -> dict:
    """
    Moving-block bootstrap 95% percentile CI for OOS R² vs zero and for
    RMSE(model) - RMSE(persistence).
    """
    y, pm = _as_arrays(y, pred_model)
    _, pb = _as_arrays(y, pred_benchmark)
    n = len(y)
    if n < block_len + 2:
        return {"boot_r2_lo": float("nan"), "boot_r2_hi": float("nan"),
                "boot_rmse_diff_lo": float("nan"), "boot_rmse_diff_hi": float("nan"),
                "boot_n": n, "boot_block_len": block_len, "boot_reps": 0}
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_len))
    offsets = np.arange(block_len)
    r2s = np.empty(n_boot, dtype=float)
    diffs = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        yy, pp, pz = y[idx], pm[idx], pb[idx]
        r2s[b] = r2_vs_zero(yy, pp)
        diffs[b] = rmse(yy, pp) - rmse(yy, pz)
    return {
        "boot_r2_lo": float(np.percentile(r2s, 2.5)),
        "boot_r2_hi": float(np.percentile(r2s, 97.5)),
        "boot_rmse_diff_lo": float(np.percentile(diffs, 2.5)),
        "boot_rmse_diff_hi": float(np.percentile(diffs, 97.5)),
        "boot_n": n,
        "boot_block_len": block_len,
        "boot_reps": n_boot,
    }


def dispersion(y, pred) -> dict:
    y, pred = _as_arrays(y, pred)
    if len(y) < 2:
        return {"std_pred": float("nan"), "std_actual": float("nan"), "corr": float("nan")}
    sp = float(np.std(pred))
    sy = float(np.std(y))
    if sp == 0 or sy == 0:
        corr = float("nan")
    else:
        corr = float(np.corrcoef(pred, y)[0, 1])
    return {"std_pred": sp, "std_actual": sy, "corr": corr}


def cost_sanity(y, costs=(0.015, 0.030)) -> dict:
    """
    Break-even directional accuracy given the mean absolute daily log move.
    Assumes one position per day, symmetric moves, no slippage/compounding.
    """
    y = np.asarray(y, dtype=float)
    avg_abs = float(np.mean(np.abs(y))) if len(y) else float("nan")
    out = {"avg_abs_move": avg_abs}
    for c in costs:
        key = f"breakeven_acc_{c:.3f}".replace(".", "_")
        out[key] = float(0.5 * (1.0 + c / avg_abs)) if avg_abs > 0 else float("inf")
    return out


def evaluate_predictions(y, pred, histmean_pred) -> dict:
    """All §7 metrics for one model on one evaluation sample."""
    y, pred = _as_arrays(y, pred)
    out = {
        "n": int(len(y)),
        "rmse": rmse(y, pred),
        "mae": mae(y, pred),
        "r2_zero": r2_vs_zero(y, pred),
        "r2_histmean": r2_vs_benchmark(y, pred, histmean_pred),
    }
    out.update(directional_accuracy(y, pred))
    out.update(diebold_mariano(y, pred, np.zeros_like(y)))
    out.update(block_bootstrap(y, pred, np.zeros_like(y)))
    out.update(dispersion(y, pred))
    return out
