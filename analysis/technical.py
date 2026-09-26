"""Technical indicator calculations. All point-in-time: values at day D depend
only on data up to the close of day D (no centre-based windows, no future
rows)."""
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    avg_up = up.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_down = down.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_up / avg_down.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = line - sig
    return pd.DataFrame({"macd": line, "signal": sig, "hist": hist})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def realized_vol(close: pd.Series, window: int, annualize: bool = True) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    vol = log_ret.rolling(window, min_periods=window).std(ddof=1)
    if annualize:
        vol = vol * np.sqrt(252)
    return vol * 100.0


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    
    up_move = df["high"] - df["high"].shift(1)
    down_move = df["low"].shift(1) - df["low"]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr_ = tr.ewm(alpha=1.0/period, adjust=False, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0/period, adjust=False, min_periods=period).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0/period, adjust=False, min_periods=period).mean() / atr_
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1.0/period, adjust=False, min_periods=period).mean()


def add_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add indicator columns to a clean OHLCV frame (lowercase cols)."""
    out = df.copy()
    close, high, low, open_ = out["close"], out["high"], out["low"], out["open"]
    ind = cfg["indicators"]

    for n in ind["ma_periods"]:
        out[f"sma_{n}"] = sma(close, n)
    for n in ind.get("ema_periods", []):
        out[f"ema_{n}"] = ema(close, n)

    out["rsi_14"] = rsi(close, ind["rsi_period"])
    m = macd(close, ind["macd"]["fast"], ind["macd"]["slow"], ind["macd"]["signal"])
    out["macd"] = m["macd"]
    out["macd_signal"] = m["signal"]
    out["macd_hist"] = m["hist"]
    out["atr_14"] = atr(out, ind["atr_period"])
    out["atr_pct"] = out["atr_14"] / close * 100.0
    out["gap_pct"] = (open_ / close.shift(1) - 1.0) * 100.0
    out["range_pct"] = (high - low) / close * 100.0
    out["vol_10d"] = realized_vol(close, 10)
    out["vol_20d"] = realized_vol(close, 20)
    out["adx_14"] = adx(out, 14)
    for w in ind["return_windows"]:
        out[f"ret_{w}d"] = close.pct_change(w) * 100.0
    return out