"""Walk-forward, no-lookahead validation of the analogue methodology.

For each day D in the test window the analogue cohort is built using ONLY days
before D, and the prediction (cohort median / prob-up) is compared with D's
actual next-day return. Predictions are benchmarked against the unconditional
next-day distribution of the same window.
"""
import time

import numpy as np
import pandas as pd

from analysis import patterns


def prepare(settings: dict, df: pd.DataFrame, lookback=None, features=None) -> tuple:
    """Build the feature frame + point-in-time z-scores once for reuse."""
    analog_cfg = settings["analogues"]
    lookback = lookback or analog_cfg["standardize_lookback"]
    features = features or analog_cfg["features"]
    frame = patterns.build_features(df, settings)
    z = patterns.zscore_point_in_time(frame, features, lookback)
    return frame, z


def evaluate(frame, z, features, weights, k, look, settings: dict) -> dict:
    """Walk-forward evaluation on precomputed frame/z. Predictions for each day
    D use ONLY days before D; compared against D's actual next-day return."""
    bt_cfg = settings["backtest"]

    n = len(frame)
    test_start = max(look + 200, n - int(bt_cfg["window_years"] * 252))
    rows = list(range(test_start, n - 1))

    records = []
    t0 = time.time()
    for p in rows:
        idxs, _ = patterns.find_analogues(frame, z, features, weights, p, k, look)
        if not idxs:
            continue
        sub = frame.iloc[idxs]
        med = float(sub["nxt_ret"].median())
        p_up = float((sub["nxt_ret"] > 0).mean())
        actual = float(frame["nxt_ret"].iloc[p])
        records.append({"date": frame.index[p], "pred_median": med, "prob_up": p_up, "actual": actual})

    pred = pd.DataFrame(records)
    res = {"ok": False, "records": pred, "seconds": round(time.time() - t0, 1)}
    if pred.empty:
        return res

    act = pred["actual"]
    res["ok"] = True
    res["n_days"] = int(len(pred))
    res["hit_rate"] = float(((pred["pred_median"] > 0) == (act > 0)).mean())
    res["always_up_acc"] = float((act > 0).mean())
    res["edge"] = res["hit_rate"] - res["always_up_acc"]
    res["corr"] = float(pred["pred_median"].corr(act))
    res["mae"] = float((pred["pred_median"] - act).abs().mean())
    res["baseline_mean"] = float(act.mean())
    res["baseline_median"] = float(act.median())
    res["baseline_std"] = float(act.std(ddof=0))

    bull_t = settings["sentiment"]["bull_threshold"]
    bear_t = settings["sentiment"]["bear_threshold"]
    strong = pred[pred["prob_up"] >= bull_t]
    weak = pred[pred["prob_up"] <= bear_t]
    res["n_strong"] = int(len(strong))
    res["n_weak"] = int(len(weak))
    res["strong_mean_actual"] = float(strong["actual"].mean()) if len(strong) else float("nan")
    res["weak_mean_actual"] = float(weak["actual"].mean()) if len(weak) else float("nan")

    sem = act.std(ddof=0) / np.sqrt(act.size)
    res["t_mean"] = float(act.mean() / sem) if sem and sem > 0 else float("nan")
    return res


def run(settings: dict, df: pd.DataFrame, k=None, lookback=None, features=None, weights=None) -> dict:
    analog_cfg = settings["analogues"]
    k = k or analog_cfg["k"]
    lookback = lookback or analog_cfg["standardize_lookback"]
    features = features or analog_cfg["features"]
    weights = weights or analog_cfg["weights"]
    frame, z = prepare(settings, df, lookback, features)
    return evaluate(frame, z, features, weights, k, lookback, settings)