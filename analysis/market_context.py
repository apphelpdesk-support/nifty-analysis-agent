"""Market context snapshot (Phase 2a).

Turns the locally cached OHLCV series into factual, point-in-time regime facts
(VIX percentile, overnight US/global returns, rates, FX, commodities). These are
statistical context ONLY — no news or interpretation. The Nifty Analyst agent
adds live items (FII/DII, GIFT Nifty, options OI/PCR, macro headlines) into the
report's Interpretation blocks via the fetch-nifty skill.

Any series that is missing/empty is simply skipped; nothing here can crash the
report.
"""
import numpy as np
import pandas as pd

import core.data as data

METRICS = {
    "india_vix": ("India VIX", "level"),
    "us_sp500": ("S&P 500", "prev session %"),
    "us_dow": ("Dow Jones", "prev session %"),
    "us_10y": ("US 10Y yield", "level"),
    "us_dxy": ("Dollar index", "level"),
    "usdinr": ("USD/INR", "level"),
    "crude_wti": ("Crude WTI", "prev session %"),
    "gold": ("Gold", "prev session %"),
}


def _percentile_1y(s: pd.Series, value: float) -> float:
    trail = s[s.index >= s.index[-1] - pd.Timedelta(days=365)]
    if trail.size < 100:
        return float("nan")
    return float((trail < value).mean() * 100.0)


def _series_context(name: str, settings: dict) -> dict:
    df = data.load_series(name, settings)
    if df.empty or "close" not in df:
        return {"available": False, "name": name}
    s = df["close"].dropna()
    if s.size < 2:
        return {"available": False, "name": name}
    last = float(s.iloc[-1])
    chg1 = float((s.iloc[-1] / s.iloc[-2] - 1.0) * 100.0)
    chg5 = float((s.iloc[-1] / s.iloc[min(5, s.size - 1)] - 1.0) * 100.0) if s.size >= 6 else float("nan")
    return {
        "available": True,
        "name": name,
        "last": last,
        "chg_1d_pct": chg1,
        "chg_5d_pct": chg5,
        "pctile_1y": _percentile_1y(s, last),
        "asof": s.index[-1],
    }


def vix_regime(level: float) -> str:
    if level < 13:
        return "Low"
    if level < 17:
        return "Normal"
    if level < 24:
        return "Elevated"
    return "High"


def context_table(settings: dict) -> pd.DataFrame:
    rows = []
    for name, (label, kind) in METRICS.items():
        c = _series_context(name, settings)
        if not c["available"]:
            continue
        chg = "" if kind == "level" else "%"
        rows.append({
            "series": label,
            "asof": c["asof"].strftime("%Y-%m-%d"),
            "value": round(c["last"], 2),
            "1d %": round(c["chg_1d_pct"], 2) if kind == "prev session %" else "",
            "5d %": round(c["chg_5d_pct"], 2) if kind == "prev session %" else "",
            "1y pctile": round(c["pctile_1y"], 0) if not np.isnan(c["pctile_1y"]) else "",
        })
    return pd.DataFrame(rows)


def context_snapshot(settings: dict) -> dict:
    """Convenience dict used by the daily report runner."""
    vix = _series_context("india_vix", settings)
    out = {
        "table": context_table(settings),
        "vix": None,
    }
    if vix["available"]:
        out["vix"] = {
            "level": round(vix["last"], 1),
            "chg_1d_pct": round(vix["chg_1d_pct"], 2),
            "pctile_1y": round(vix["pctile_1y"], 0),
            "regime": vix_regime(vix["last"]),
        }
    return out