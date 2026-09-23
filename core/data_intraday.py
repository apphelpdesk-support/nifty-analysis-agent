"""Intraday data: free 60-day yfinance collector + optional Zerodha Kite
backfill + generic bulk-CSV importer.

Canonical archive is the 5-minute bar file  data/intraday/5m/<name>.csv
(tz-aware Asia/Kolkata DatetimeIndex, columns open/high/low/close/volume).
15/30/60m frames are derived on load by session-aware resampling.

Data provenance:
  * recent bars (last ~60 days): yfinance, volume = aggregated index volume
  * deep bars (2015-01-09+): Zerodha Kite index API, volume = 0 (index has none)
  * optional: bulk CSV import (Dukascopy / Kaggle / any OHLCV file)
"""
import time
from pathlib import Path

import pandas as pd

import core.settings as settings_mod
from core import session


def archive_path(name: str, settings: dict, minutes: int = 5) -> Path:
    return settings_mod.rel(settings, "intraday_archive_dir") / f"{minutes}m" / f"{name}.csv"


def _finalize(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df.index = session.to_aware(df.index, tz)
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep]
    o_min, c_min = session.open_min({"open": "09:15"}), session.close_min({"close": "15:30"})
    mins = df.index.hour * 60 + df.index.minute
    df = df[(mins >= o_min) & (mins <= c_min)]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def load_bars(name: str, minutes: int, settings: dict) -> pd.DataFrame:
    p = archive_path(name, settings, minutes)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    return _finalize(df, session.session_cfg(settings)["tz"])


def _save_bars(df: pd.DataFrame, name: str, settings: dict, minutes: int = 5) -> Path:
    p = archive_path(name, settings, minutes)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p)
    return p


def update_from_yfinance(name: str, symbol: str, settings: dict, days: int = None) -> pd.DataFrame:
    """Refetch the rolling ~60-day 5-minute window from Yahoo and merge it into
    the canonical archive. Idempotent; cheap; no credentials."""
    days = days or settings["intraday"]["yfinance_depth_days"]
    import yfinance as yf

    try:
        raw = yf.Ticker(symbol).history(
            period=f"{days}d", interval="5m", auto_adjust=False, actions=False, timeout=30
        )
    except Exception as exc:
        print(f"[intraday] yfinance fetch failed for {symbol}: {exc}")
        raw = pd.DataFrame()
    tz = session.session_cfg(settings)["tz"]
    fresh = _finalize(raw, tz)
    if fresh.empty:
        print(f"[intraday] no recent bars for {symbol}")
        return load_bars("nifty", 5, settings)

    fresh.index.name = "ts"
    existing = load_bars("nifty", 5, settings)
    combined = pd.concat([existing.reset_index(), fresh.reset_index()]).drop_duplicates(subset=["ts"], keep="last")
    combined = combined.set_index("ts").sort_index()
    _save_bars(combined, name, settings, 5)
    print(f"[intraday] {name}: {len(combined)} 5m bars archived (last {days}d from yfinance)")
    return combined


def update_all_free(settings: dict) -> None:
    syms = settings["symbols"]
    for name, symbol in [("nifty", syms["nifty"]), ("bank_nifty", syms["bank_nifty"])]:
        update_from_yfinance(name, symbol, settings)
    print("[intraday] free collector done.")


def import_bulk_csv(csv_path, name: str, settings: dict, minutes: int = 5) -> Path:
    """Import an OHLCV CSV (columns open,high,low,close,volume; index parseable
    datetime) into the canonical archive after session filtering."""
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    if "Adj Close" in df.columns:
        df = df.drop(columns=["Adj Close"])
    df.columns = [c.lower().strip() for c in df.columns]
    tz = session.session_cfg(settings)["tz"]
    clean = _finalize(df, tz)
    existing = load_bars(name, 5, settings)
    combined = pd.concat([existing.reset_index(), clean.reset_index()]).drop_duplicates(subset=["ts"], keep="last")
    combined = combined.set_index("ts").sort_index()
    return _save_bars(combined, name, settings, minutes)