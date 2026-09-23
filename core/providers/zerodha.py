"""Zerodha Kite Connect intraday backfill (optional).

Needs config/kite.ini (gitignored):
    [kite]
    api_key = ...
    api_secret = ...
    access_token = ...        # minted once by `--login` below

Flow: user runs scripts/backfill_intraday.py --login, opens the printed auth URL
in their browser, approves, pastes the request_token back; the script exchanges
it for an access_token and stores it. The backfill then pulls NIFTY 50 index
5-minute bars (token 256265) from 2015-01-09 in month chunks into the archive.

The index has no volume on Kite; deep bars therefore get volume = 0. Recent bars
(with volume) are blended in from the free yfinance collector.
"""
import configparser
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import core.settings as settings_mod
from core import data_intraday, session


def ini_path(settings: dict) -> Path:
    return settings_mod.ROOT / settings["intraday"]["kite"]["config"]


def load_config(settings: dict) -> configparser.ConfigParser | None:
    p = ini_path(settings)
    if not p.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(p)
    return cfg


def _client(settings: dict):
    cfg = load_config(settings)
    if cfg is None:
        raise RuntimeError("config/kite.ini not found. Run scripts/backfill_intraday.py --login first.")
    import kiteconnect

    api_key = cfg["kite"]["api_key"]
    access_token = cfg["kite"]["access_token"]
    kc = kiteconnect.KiteConnect(api_key=api_key)
    kc.set_access_token(access_token)
    return kc, cfg


def login(settings: dict) -> None:
    cfg = load_config(settings)
    if cfg is None:
        api_key = input("api_key: ").strip()
        api_secret = input("api_secret: ").strip()
        cfg = configparser.ConfigParser()
        cfg["kite"] = {"api_key": api_key, "api_secret": api_secret, "access_token": ""}
    import kiteconnect

    kc = kiteconnect.KiteConnect(api_key=cfg["kite"]["api_key"])
    print("Open this URL in your browser and log in / approve:")
    print(kc.login_url())
    request_token = input("Paste the request_token from the redirect URL: ").strip()
    data = kc.generate_session(request_token, api_secret=cfg["kite"]["api_secret"])
    cfg["kite"]["access_token"] = data["access_token"]
    p = ini_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        cfg.write(fh)
    print(f"Access token saved to {p} (token expires ~1 day; re-login to refresh).")


def _fetch_chunk(kc, token, from_dt, to_dt, interval="5minute") -> pd.DataFrame:
    candles = kc.historical_data(token, from_dt, to_dt, interval=interval, continuous=0, oi=0)
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df = df.rename(columns={"date": "ts", "volume": "volume"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("ts")
    df["volume"] = 0  # index has no traded volume on Kite
    return df[["open", "high", "low", "close", "volume"]]


def backfill(settings: dict, name: str = "nifty", verbose: bool = True) -> Path:
    """Pull month-by-month 5-minute bars from Kite and merge into the archive."""
    cfg = settings["intraday"]["kite"]
    kc, _ = _client(settings)
    token = cfg["index_token"]
    start = pd.Timestamp(cfg["backfill_start"], tz="Asia/Kolkata")

    existing = data_intraday.load_bars(name, 5, settings)
    if not existing.empty:
        start = existing.index.max().tz_convert("Asia/Kolkata") + pd.Timedelta(minutes=5)

    now = pd.Timestamp.now(tz="Asia/Kolkata")
    frames, cursor = [], start
    while cursor < now:
        nxt = (cursor + pd.offsets.MonthEnd(1)).normalize() + pd.offsets.Day(1)
        if nxt > now:
            nxt = now
        df = _fetch_chunk(kc, token, cursor, nxt)
        if verbose:
            print(f"[kite] {cursor:%Y-%m-%d} -> {nxt:%Y-%m-%d}: {len(df)} bars")
        if not df.empty:
            frames.append(df)
        cursor = nxt
        time.sleep(0.4)

    if not frames:
        print("[kite] nothing new to backfill")
        return data_intraday.archive_path(name, settings, 5)

    combined = pd.concat([existing] + frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    tz = session.session_cfg(settings)["tz"]
    combined.index = combined.index.tz_convert(tz)
    return data_intraday._save_bars(combined, name, settings, 5)