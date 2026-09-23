"""Nifty options context (Phase 2b).

Reads whatever is cached under data/options/ (the agent drops NSE options
snapshots there via the fetch-nifty skill). If nothing is present, all calls
return available=False gracefully so the report never breaks.

Expected CSV shape (columns may vary): a date/time column, plus put/call OI
columns (pe_oi/ce_oi or put_oi/call_oi); PCR is derived when not present.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import core.settings as settings_mod


def _load_all(settings: dict) -> pd.DataFrame:
    folder = settings_mod.rel(settings, "options_dir")
    files = sorted(folder.glob("*.csv")) if folder.exists() else []
    frames = []
    for p in files:
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except Exception:
            continue
        df = df[~df.index.isna()]
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_index()


def pcr_series(settings: dict) -> pd.Series:
    df = _load_all(settings)
    if df.empty:
        return pd.Series(dtype=float)
    pe = df.get("pe_oi", df.get("put_oi"))
    ce = df.get("ce_oi", df.get("call_oi"))
    if pe is None or ce is None or "pcr" not in df:
        if pe is None or ce is None:
            return pd.Series(dtype=float)
        return (pe / ce.replace(0, np.nan)).dropna()
    return df["pcr"].dropna().astype(float)


def snapshot(settings: dict) -> dict:
    """Latest PCR + regime vs trailing 90d, or {'available': False}."""
    s = pcr_series(settings)
    if s.empty:
        return {"available": False}
    last = float(s.iloc[-1])
    trail = s[s.index >= s.index[-1] - pd.Timedelta(days=120)]
    pctile = float((trail < last).mean() * 100.0) if trail.size >= 30 else float("nan")
    regime = "Calls-heavy" if last < 1.0 else ("Puts-heavy" if last > 1.2 else "Balanced")
    return {
        "available": True,
        "last": round(last, 3),
        "asof": s.index[-1],
        "pctile_120d": round(pctile, 0),
        "regime": regime,
        "n_days": int(s.size),
    }