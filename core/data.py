"""Historical data download & caching using yfinance.

All downloads are cached to data/historical/<name>.csv as daily OHLCV rows
(indexed by YYYY-MM-DD). update_history() is incremental: it resumes from the
last cached row and only fetches what is missing.
"""
import re
import time
from pathlib import Path

import pandas as pd

import core.settings as settings_mod

# Readable cache names for the auxiliary series (us_markets / global).
SYMBOL_NAMES = {
    "^GSPC": "us_sp500",
    "^IXIC": "us_nasdaq",
    "^DJI": "us_dow",
    "^TNX": "us_10y",
    "DX-Y.NYB": "us_dxy",
    "INR=X": "usdinr",
    "CL=F": "crude_wti",
    "GC=F": "gold",
}


def readable_name(symbol: str) -> str:
    if symbol in SYMBOL_NAMES:
        return SYMBOL_NAMES[symbol]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_").lower()
    return slug or "series"


def rows_to_date_index(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        try:
            idx = idx.tz_convert("Asia/Kolkata")
        except Exception:
            pass
    df = df.copy()
    df.index = pd.to_datetime([d.strftime("%Y-%m-%d") for d in idx], errors="coerce")
    return df


def ohlcv_path(name: str, settings: dict) -> Path:
    return settings_mod.rel(settings, "historical_dir") / f"{name}.csv"


def load_series(name: str, settings: dict) -> pd.DataFrame:
    p = ohlcv_path(name, settings)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    if "close" in df:
        df = df.dropna(subset=["close"])
    return df


def save_series(name: str, df: pd.DataFrame, settings: dict) -> Path:
    p = ohlcv_path(name, settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p)
    return p


def fetch_symbol(symbol: str, start: str, end=None, delay: float = 0.5) -> pd.DataFrame:
    """Fetch OHLCV for a symbol; returns clean daily df or empty on failure."""
    import yfinance as yf

    time.sleep(delay)
    try:
        df = yf.Ticker(symbol).history(
            start=start, end=end, auto_adjust=False, actions=False, timeout=20
        )
    except Exception as exc:
        print(f"[data] fetch failed for {symbol}: {exc}")
        return pd.DataFrame()
    if df is None or df.empty:
        print(f"[data] no rows for {symbol}")
        return pd.DataFrame()

    df = rows_to_date_index(df)
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[keep]
    df.columns = [c.lower() for c in df.columns]
    df = df[~df.index.isna()]
    df = df[~df.index.duplicated(keep="last")]
    return df.sort_index()


def update_history(name: str, symbol: str, settings: dict, start=None, end=None) -> pd.DataFrame:
    existing = load_series(name, settings)
    start = start or settings["data"].get("start_date", "2004-01-01")
    if not existing.empty:
        resume = existing.index.max()
        start = (resume + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"[data] {name}: cache up to {resume:%Y-%m-%d}, fetching since {start}")
    else:
        print(f"[data] {name}: no cache, full download from {start}")
    fetched = fetch_symbol(symbol, start=start, end=end)
    if fetched.empty:
        if existing.empty:
            print(f"[data] WARNING: no data obtained for {name} ({symbol})")
        else:
            print(f"[data] {name}: nothing new to fetch")
        return existing

    combined = pd.concat([existing, fetched])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    save_series(name, combined, settings)
    print(f"[data] {name}: {len(combined)} rows cached -> {ohlcv_path(name, settings)}")
    return combined


def update_all(settings: dict) -> None:
    syms = settings["symbols"]
    for name, symbol in [
        ("nifty", syms["nifty"]), ("bank_nifty", syms["bank_nifty"]), ("india_vix", syms["india_vix"]),
    ]:
        update_history(name, symbol, settings)
    for symbol in syms.get("us_markets", []):
        update_history(readable_name(symbol), symbol, settings)
    for symbol in syms.get("global", []):
        update_history(readable_name(symbol), symbol, settings)


def save_daily_snapshots(settings: dict) -> None:
    out = settings_mod.rel(settings, "daily_dir")
    out.mkdir(parents=True, exist_ok=True)
    for p in sorted(settings_mod.rel(settings, "historical_dir").glob("*.csv")):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if df.empty:
            continue
        df.iloc[-1:].copy().to_csv(out / p.name)
    print(f"[data] daily snapshots written to {out}")