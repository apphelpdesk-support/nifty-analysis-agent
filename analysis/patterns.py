"""Similar-historical-day detection and next-day outcome analysis.

Everything here is point-in-time:
  * features at day D only use data up to the close of D,
  * analogues for D are drawn strictly from days BEFORE D,
  * z-scoring uses a trailing lookback window (never full-sample stats).
No future information is ever used.
"""
import numpy as np
import pandas as pd

from analysis import technical


def build_features(df: pd.DataFrame, cfg: dict, ma_periods=None) -> pd.DataFrame:
    """Work frame: indicators + feature columns + next-day outcome columns."""
    ind = dict(cfg["indicators"])
    if ma_periods:
        ind["ma_periods"] = list(ma_periods)
    sub_cfg = dict(cfg)
    sub_cfg["indicators"] = ind
    out = technical.add_indicators(df, sub_cfg)

    close, high, low, open_ = out["close"], out["high"], out["low"], out["open"]
    for n in ind["ma_periods"]:
        out[f"dist_sma{n}"] = (close / out[f"sma_{n}"] - 1.0) * 100.0
    out["macd_hist_pct"] = out["macd_hist"] / close * 100.0

    # Calendar / session meta features (point-in-time by construction).
    idx = out.index
    out["dow_monday"] = (idx.dayofweek == 0).astype(int)
    dom = idx.day
    dim = idx.days_in_month
    out["days_to_month_end"] = dim - dom
    out["expiry_zone"] = (out["days_to_month_end"] <= 5).astype(int)

    out["nxt_close"] = close.shift(-1)
    out["nxt_open_gap"] = (open_.shift(-1) / close - 1.0) * 100.0
    out["nxt_ret"] = (close.shift(-1) / close - 1.0) * 100.0
    out["nxt_high_pct"] = (high.shift(-1) / close - 1.0) * 100.0
    out["nxt_low_pct"] = (low.shift(-1) / close - 1.0) * 100.0
    out["nxt_maf"] = out["nxt_high_pct"].clip(lower=0.0)
    out["nxt_mad"] = out["nxt_low_pct"].clip(upper=0.0)
    return out


def zscore_point_in_time(frame: pd.DataFrame, features, lookback: int) -> pd.DataFrame:
    """Point-in-time z-scores: each row is standardized by the trailing window
    ending at that row (rolling mean/std, never full-sample statistics)."""
    minp = min(lookback, 60)
    z = pd.DataFrame(index=frame.index)
    for f in features:
        col = frame[f].astype(float)
        mean = col.rolling(lookback, min_periods=minp).mean()
        std = col.rolling(lookback, min_periods=minp).std(ddof=0)
        z[f] = (col - mean) / std.replace(0, np.nan)
    return z


def find_analogues(
    frame: pd.DataFrame,
    z: pd.DataFrame,
    features,
    weights,
    target_pos: int,
    k: int,
    standardize_lookback: int,
):
    """Top-k most similar historical days strictly BEFORE target_pos.

    Similarity = weighted Euclidean distance on point-in-time z-scored features.
    Returns (positions, distances).
    """
    feats = np.array([z[f].to_numpy(dtype=float) for f in features]).T
    w = np.array([weights.get(f, 1.0) for f in features], dtype=float)
    target = feats[target_pos]
    mask = ~np.isnan(feats).any(axis=1)
    cand_idx = np.flatnonzero(mask)
    cand_idx = cand_idx[cand_idx < target_pos]
    if cand_idx.size == 0:
        return [], []
    cand = feats[cand_idx]
    diff = (cand - target) * w
    dist = np.sqrt(np.einsum("ij,ij->i", diff, diff))
    order = np.argsort(dist)[:k]
    return cand_idx[order].tolist(), dist[order].tolist()


OUTCOME_METRICS = ["nxt_open_gap", "nxt_ret", "nxt_high_pct", "nxt_low_pct", "nxt_mad", "nxt_maf"]


def outcome_stats(sub: pd.DataFrame) -> dict:
    """Aggregate distribution of next-day outcomes for a cohort of analogues."""
    stats = {}
    for col in OUTCOME_METRICS:
        s = sub[col].dropna()
        if s.empty:
            stats[col] = {"count": 0}
            continue
        stats[col] = {
            "count": int(s.size),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "std": float(s.std(ddof=0)),
            "p5": float(s.quantile(0.05)),
            "p25": float(s.quantile(0.25)),
            "p75": float(s.quantile(0.75)),
            "p95": float(s.quantile(0.95)),
        }
    r = sub["nxt_ret"].dropna()
    if r.empty:
        stats["direction"] = {"up": 0, "down": 0, "flat": 0, "prob_up": float("nan")}
    else:
        stats["direction"] = {
            "up": int((r > 0).sum()),
            "down": int((r < 0).sum()),
            "flat": int((r == 0).sum()),
            "prob_up": float((r > 0).mean()),
        }
    stats["dates"] = [d.strftime("%Y-%m-%d") for d in sub.index]
    return stats


def _mad(s: pd.Series) -> float:
    med = s.median()
    return float((s - med).abs().median())


def divergence(frame: pd.DataFrame, sub: pd.DataFrame, feature_cols) -> pd.DataFrame:
    """Current day value vs analogue median/robust spread for each feature (raw scale)."""
    rows = []
    for f in feature_cols:
        today = float(frame[f].iloc[-1]) if pd.notna(frame[f].iloc[-1]) else float("nan")
        med = float(sub[f].median()) if sub[f].notna().any() else float("nan")
        mad = _mad(sub[f]) if sub[f].notna().any() else float("nan")
        rows.append({"feature": f, "today": round(today, 3), "analogue_median": round(med, 3), "analogue_mad": round(mad, 3)})
    return pd.DataFrame(rows)


def scenarios(stats: dict, sentiment_cfg: dict) -> dict:
    """Derive bullish / neutral / bearish scenario bands strictly from the
    analogue distribution. Interpretation (news, internals) is added later by
    the orchestrating agent, not here."""
    nxt = stats.get("nxt_ret", {})
    if not nxt or not nxt.get("count"):
        return {}
    prob_up = stats["direction"]["prob_up"]
    bull_t = sentiment_cfg["bull_threshold"]
    bear_t = sentiment_cfg["bear_threshold"]
    if prob_up >= bull_t:
        bias = "Bullish"
    elif prob_up <= bear_t:
        bias = "Bearish"
    else:
        bias = "Neutral"

    r = stats["dates"]  # noqa: F841 - kept for symmetry; not needed below
    return {
        "bias": bias,
        "prob_up": round(prob_up, 3),
        "prob_down": round(1.0 - prob_up, 3),
        "central_case": nxt["median"],
        "median_band": [nxt["p25"], nxt["p75"]],
        "full_range": [nxt["p5"], nxt["p95"]],
        "bullish_scenario": {"prob": round(max(prob_up, 1 - prob_up), 3), "target_median_ret": nxt["p75"]},
        "bearish_scenario": {"prob": round(min(prob_up, 1 - prob_up), 3), "target_median_ret": nxt["p25"]},
    }


def auto_select_features(
    frame: pd.DataFrame,
    z: pd.DataFrame,
    available_features: list,
    weights: dict,
    target_pos: int,
    k: int,
    standardize_lookback: int,
    backtest_days: int = 60,
    top_n: int = 5,
) -> tuple:
    """
    Evaluates individual features over the last `backtest_days` to determine which ones
    yield the highest win-rate (accuracy of prob_up predicting nxt_ret direction).
    Returns the top N feature names and their accuracy scores.
    """
    scores = {}
    for f in available_features:
        correct = 0
        valid_days = 0
        
        for pos in range(max(1, target_pos - backtest_days), target_pos):
            idx, dist = find_analogues(frame, z, [f], weights, pos, k, standardize_lookback)
            if not idx:
                continue
            
            cohort_ret = frame["nxt_ret"].iloc[idx]
            prob_up = (cohort_ret > 0).mean()
            predicted_up = prob_up > 0.5
            actual_up = frame["nxt_ret"].iloc[pos] > 0
            
            if predicted_up == actual_up:
                correct += 1
            valid_days += 1
            
        acc = correct / valid_days if valid_days > 0 else 0.0
        scores[f] = acc
        
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_features = [f for f, acc in ranked[:top_n]]
    return best_features, scores