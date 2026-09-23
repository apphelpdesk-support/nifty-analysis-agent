"""Intraday bar-level features and forward-outcomes (5/15/30/60m agnostic).

Everything is point-in-time: features at bar t use only bars <= t (plus prior
session close and earlier daily data). Forward outcomes come strictly from bars
AFTER t within the same session; rows without a valid outcome (session-final
bars) get NaN and are excluded from candidate pools.
"""
import numpy as np
import pandas as pd

from analysis import technical
from core import session


def _detect_tf(bars: pd.DataFrame, settings: dict) -> int:
    if len(bars) > 1:
        seconds = (bars.index[1] - bars.index[0]).total_seconds()
        if seconds > 0:
            return int(round(seconds / 60))
    return settings["intraday"]["timeframes_minutes"][0]


def _roll_extreme(grouped, col, n, direction: str) -> pd.Series:
    parts = [grouped[col].shift(-i) for i in range(1, n + 1)]
    frame = pd.concat(parts, axis=1)
    if direction == "high":
        return frame.max(axis=1, skipna=True)
    return frame.min(axis=1, skipna=True)


def _session_last_mask(out: pd.DataFrame) -> pd.Series:
    tails = out.groupby("session")["close"].tail(1).index
    return out.index.isin(tails)


def build_features(bars: pd.DataFrame, daily: pd.DataFrame, settings: dict) -> pd.DataFrame:
    cfg = settings["intraday"]
    tz = cfg["session"]["tz"]
    tf = _detect_tf(bars, settings)
    scfg = cfg["session"]

    out = bars.copy()
    out.index = session.to_aware(out.index, tz)
    out["session"] = pd.to_datetime(out.index.date)
    g = out.groupby("session")

    bpd = session.bars_per_day(tf, settings)
    o_min = session.open_min(scfg)
    c_min = session.close_min(scfg)
    starts = out.index.hour * 60 + out.index.minute
    out["bar_no"] = ((starts - o_min) // tf).astype(float)
    out["time_in_session"] = (starts - o_min) / (c_min - o_min)

    sess_open = g["open"].transform("first")
    out["cum_ret_since_open"] = (out["close"] / sess_open - 1.0) * 100.0
    out["dist_from_open"] = (out["close"] / sess_open - 1.0) * 100.0

    # Session VWAP (volume=0 on deep Kite bars -> equal-weighted TP fallback)
    tp = (out["high"] + out["low"] + out["close"]) / 3.0
    vol = out["volume"].fillna(0)
    pv = tp * vol
    cpv = pv.groupby(out["session"]).cumsum()
    cv = vol.groupby(out["session"]).cumsum()
    cnt = out.groupby("session").cumcount() + 1
    tp_mean = tp.groupby(out["session"]).cumsum() / cnt
    vwap = (cpv / cv.replace(0, np.nan)).fillna(tp_mean)
    out["dist_vwap"] = (out["close"] / vwap - 1.0) * 100.0

    out["gap_pct"] = (out["open"] / out["close"].shift(1) - 1.0) * 100.0
    out.loc[out["bar_no"] != 0, "gap_pct"] = np.nan
    out["gap_pct"] = out.groupby("session")["gap_pct"].ffill()  # session-wide context

    out["ret_1bar"] = g["close"].pct_change() * 100.0
    rw = max(1, min(6, bpd - 2))
    out["ret_6bar"] = g["close"].pct_change(rw) * 100.0
    tr = pd.concat(
        [out["high"] - out["low"], (out["high"] - out["close"].shift(1)).abs(), (out["low"] - out["close"].shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1.0 / 14, adjust=False, min_periods=14).mean()
    out["atr_pct"] = out["atr_14"] / out["close"] * 100.0
    out["rsi_14"] = technical.rsi(out["close"], 14)
    lr = np.log(out["close"] / out["close"].shift(1))
    out["vol_14"] = lr.rolling(14, min_periods=14).std(ddof=1) * np.sqrt(252 * bpd) * 100.0

    # Daily context: previous day's volume regime + return (strictly lagged).
    dv = daily.copy()
    vol_s = dv["volume"].astype(float)
    ro = dv["volume"].rolling(cfg["daily_vol_lookback"], min_periods=60)
    dv["daily_vol_z"] = ((vol_s - ro.mean()) / ro.std(ddof=0)).shift(1)
    dv["daily_ret_prev"] = (dv["close"].pct_change() * 100.0).shift(1)
    dv["session"] = pd.to_datetime(pd.to_datetime(dv.index).date)
    dv = dv.set_index("session")
    out = out.join(dv[["daily_vol_z", "daily_ret_prev"]], on="session")

    out["dow_monday"] = (pd.Series(out.index.dayofweek) == 0).astype(int).values
    out["days_to_month_end"] = (out.index.days_in_month - out.index.day)
    out["expiry_zone"] = (out["days_to_month_end"] <= 5).astype(int)

    # Forward outcomes (within-session only).
    hlist = cfg["horizon_bars"]
    for h in hlist:
        out[f"fwd_ret_{h}"] = (g["close"].shift(-h) / out["close"] - 1.0) * 100.0
        out[f"fwd_high_{h}"] = (_roll_extreme(g, "high", h, "high") / out["close"] - 1.0) * 100.0
        out[f"fwd_low_{h}"] = (_roll_extreme(g, "low", h, "low") / out["close"] - 1.0) * 100.0
    sess_end = g["close"].transform("last")
    out["rest_of_session"] = (sess_end / out["close"] - 1.0) * 100.0
    out["fwd_ret_1"] = (g["close"].shift(-1) / out["close"] - 1.0) * 100.0

    out["is_session_last"] = _session_last_mask(out)
    out.loc[out["is_session_last"], "rest_of_session"] = np.nan
    return out


def select_valid(frame: pd.DataFrame, features) -> pd.DataFrame:
    need = features + ["fwd_ret_1", "rest_of_session"]
    return frame.dropna(subset=need)


def cohort_metrics(sub: pd.DataFrame, horizons, primary="rest_of_session") -> dict:
    metrics = [primary, "fwd_ret_1"] + [f"fwd_ret_{h}" for h in horizons]
    res = {}
    for col in metrics:
        s = sub[col].dropna()
        if s.empty:
            continue
        res[col] = {
            "count": int(s.size), "mean": float(s.mean()), "median": float(s.median()),
            "std": float(s.std(ddof=0)),
            "p5": float(s.quantile(0.05)), "p25": float(s.quantile(0.25)),
            "p75": float(s.quantile(0.75)), "p95": float(s.quantile(0.95)),
        }
    r = sub["rest_of_session"].dropna()
    res["direction"] = {
        "up": int((r > 0).sum()), "down": int((r < 0).sum()), "flat": int((r == 0).sum()),
        "prob_up": float((r > 0).mean()) if r.size else float("nan"),
    }
    return res