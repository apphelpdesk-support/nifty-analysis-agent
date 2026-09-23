"""NSE intraday session model.

All intraday bar data lives on a tz-aware Asia/Kolkata DatetimeIndex. The
session runs 09:15-15:30 IST (75 x 5-minute bars). Session-aware resampling is
used to derive 15/30/60m frames from the canonical 5m archive without ever
creating bars that bridge two sessions.
"""
import pandas as pd

from core import settings as settings_mod


def session_cfg(settings: dict) -> dict:
    return settings["intraday"]["session"]


def open_min(cfg) -> int:
    h, m = cfg["open"].split(":")
    return int(h) * 60 + int(m)


def close_min(cfg) -> int:
    h, m = cfg["close"].split(":")
    return int(h) * 60 + int(m)


def to_aware(idx, tz: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    if idx.tz is None:
        return idx.tz_localize(tz)
    return idx.tz_convert(tz)


def bars_per_day(minutes: int, settings: dict) -> int:
    cfg = session_cfg(settings)
    return int((close_min(cfg) - open_min(cfg)) / minutes)


def bar_no_in_session(idx, minutes: int, tz: str) -> pd.Series:
    """Bar ordinal within each session (0-based), from the bar start time."""
    t = idx.time
    res = []
    o_min = open_min({"open": "09:15"})
    for ts in idx:
        start = ts.hour * 60 + ts.minute
        b = max(0, (start - o_min) // minutes)
        res.append(b)
    return pd.Series(res, index=idx)


def session_label(idx) -> pd.Series:
    return pd.Series(pd.to_datetime(idx).date, index=idx)


def resample_ohlcv(df: pd.DataFrame, minutes: int, settings: dict) -> pd.DataFrame:
    """Session-aware OHLCV resample from the canonical 5m archive.

    Bars that would bridge two sessions are never created: resampling runs per
    session day, and any bar that does not end by the session close is dropped.
    """
    cfg = session_cfg(settings)
    tz = cfg["tz"]
    out = df.copy()
    out.index = to_aware(out.index, tz)
    out["_session"] = out.index.date

    agg = (
        out.groupby("_session", group_keys=False)
        .resample(f"{minutes}min", origin="start", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    )
    agg = agg[~agg.index.isna()].dropna(subset=["open", "close"])

    o_min, c_min = open_min(cfg), close_min(cfg)
    mins = agg.index.hour * 60 + agg.index.minute
    ok = (mins >= o_min) & (mins + minutes <= c_min)
    agg = agg[ok]
    agg.index.name = "ts"
    return agg


def archive_bars(name: str, minutes: int, settings: dict) -> pd.DataFrame:
    """Load 5m canonical archive and resample to the requested timeframe."""
    from core import data_intraday

    base = data_intraday.load_bars(name, 5, settings)
    if base.empty:
        return base
    if minutes == 5:
        df = base.copy()
        df.index.name = "ts"
        return df
    return resample_ohlcv(base, minutes, settings)