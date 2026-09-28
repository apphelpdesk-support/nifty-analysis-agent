"""Intraday session invariants.

Guards the two properties the whole raw-5m -> resample -> WFO architecture
depends on:

  1. Derived timeframes anchor at the session open (09:15), not midnight, and
     never emit a truncated end-of-session bin.
  2. The 5,000-bar cap is applied to raw 5m bars *before* resampling, so every
     timeframe covers the same calendar span.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.settings as settings_mod
from core import session as ss

TZ = "Asia/Kolkata"
OPEN_M, CLOSE_M = 9 * 60 + 15, 15 * 60 + 30

# 375-minute session -> whole bars per day at each timeframe.
EXPECTED_BARS_PER_DAY = {5: 75, 15: 25, 30: 12, 60: 6}

# Last whole bar start on a full session, per timeframe.
EXPECTED_LAST_BAR = {5: "15:25", 15: "15:15", 30: "14:45", 60: "14:15"}


@pytest.fixture(scope="module")
def settings():
    return settings_mod.load_settings()


def _session_stamps(days, start_h, start_m, n):
    return pd.DatetimeIndex(
        [ts for d in days for ts in pd.date_range(
            d + pd.Timedelta(hours=start_h, minutes=start_m), periods=n, freq="5min"
        )],
        tz=TZ,
    )


def _ohlcv(idx) -> pd.DataFrame:
    n = len(idx)
    return pd.DataFrame(
        {
            "open": range(n),
            "high": range(1, n + 1),
            "low": range(n),
            "close": range(1, n + 1),
            "volume": 1000,
        },
        index=idx,
    )


def synthetic_5m(n_days: int = 8) -> pd.DataFrame:
    """Regular-session 5m bars only (09:15..15:25), no pre-open rows."""
    return _ohlcv(_session_stamps(pd.bdate_range("2026-01-01", periods=n_days), 9, 15, 75))


def synthetic_with_preopen(n_days: int = 4) -> pd.DataFrame:
    """5m bars including 09:05/09:10 pre-open rows, as the Fyers feed does."""
    days = pd.bdate_range("2026-01-01", periods=n_days)
    pre = _session_stamps(days, 9, 5, 2)
    reg = _session_stamps(days, 9, 15, 75)
    return _ohlcv(pre.append(reg))


# --- anchor + bin-integrity -------------------------------------------------

@pytest.mark.parametrize("minutes", [15, 30, 60])
def test_resample_anchors_at_session_open(settings, minutes):
    out = ss.resample_ohlcv(synthetic_5m(), minutes, settings)
    first_of_day = out.groupby(out.index.date).head(1)
    assert (first_of_day.index.hour * 60 + first_of_day.index.minute == OPEN_M).all()


@pytest.mark.parametrize("minutes", [15, 30, 60])
def test_resample_never_bridges_sessions(settings, minutes):
    out = ss.resample_ohlcv(synthetic_5m(), minutes, settings)
    counts = out.groupby(out.index.date).size()
    assert (counts == EXPECTED_BARS_PER_DAY[minutes]).all()


@pytest.mark.parametrize("minutes", [5, 15, 30, 60])
def test_resample_last_bar_is_not_truncated(settings, minutes):
    """A bar must end by the session close, and the last one must be whole.

    The pre-fix midnight-anchored resample left a short 15:00 bin at 60m
    holding only 15:00-15:25, and a partial 09:00 bin at 30m/60m.
    """
    out = ss.resample_ohlcv(synthetic_5m(), minutes, settings)
    last_of_day = out.groupby(out.index.date).tail(1)
    starts = last_of_day.index.hour * 60 + last_of_day.index.minute
    assert (starts + minutes <= CLOSE_M).all()
    hh, mm = EXPECTED_LAST_BAR[minutes].split(":")
    assert (last_of_day.index.hour == int(hh)).all()
    assert (last_of_day.index.minute == int(mm)).all()


def test_60m_has_six_not_seven_bars_per_day(settings):
    """Regression guard: midnight anchoring yielded 7 bins, session anchoring 6."""
    out = ss.resample_ohlcv(synthetic_5m(), 60, settings)
    counts = out.groupby(out.index.date).size()
    assert set(counts.unique()) == {6}


def test_resample_ohlcv_is_correct_at_30m(settings):
    """A 30m bar must aggregate its own 5m bars, in order."""
    base = synthetic_5m(n_days=1)
    out = ss.resample_ohlcv(base, 30, settings)
    first = out.iloc[0]
    src = base.iloc[0:6]
    assert first["open"] == src["open"].iloc[0]
    assert first["high"] == src["high"].max()
    assert first["low"] == src["low"].min()
    assert first["close"] == src["close"].iloc[-1]
    assert first["volume"] == src["volume"].sum()


# --- shared window ----------------------------------------------------------

def test_filter_session_drops_preopen_rows(settings):
    raw = synthetic_with_preopen()
    assert len(raw) == 4 * 77
    clean = ss.filter_session(raw, settings)
    assert len(clean) == 4 * 75
    starts = clean.index.hour * 60 + clean.index.minute
    assert starts.min() == OPEN_M
    assert starts.max() == CLOSE_M - 5


def test_cap_raw_bars_trims_to_configured_limit(settings):
    limit = settings["intraday"]["max_raw_bars_5m"]
    full = synthetic_5m(n_days=70)
    assert len(full) > limit
    capped = ss.cap_raw_bars(full, settings)
    assert len(capped) == limit
    assert capped.index[0] == full.index[-limit]


def test_cap_raw_bars_is_noop_below_limit(settings):
    small = synthetic_5m(n_days=2)
    assert len(ss.cap_raw_bars(small, settings)) == len(small)


def test_all_timeframes_share_one_calendar_span(settings):
    """The point of capping raw 5m: every TF must cover the same window.

    Capping each timeframe independently would give 5m ~67 days but 60m
    ~467 bars spanning a completely different, much longer history.
    """
    raw = synthetic_5m(n_days=70)
    capped = ss.cap_raw_bars(raw, settings)
    assert len(capped) == settings["intraday"]["max_raw_bars_5m"]
    spans = {}
    for minutes in (5, 15, 30, 60):
        out = capped if minutes == 5 else ss.resample_ohlcv(capped, minutes, settings)
        spans[minutes] = (out.index[0].date(), out.index[-1].date())
    assert len(set(spans.values())) == 1, spans


def test_timeframe_bar_counts_match_expectation(settings):
    raw = ss.cap_raw_bars(synthetic_5m(n_days=70), settings)
    for minutes, per_day in EXPECTED_BARS_PER_DAY.items():
        out = raw if minutes == 5 else ss.resample_ohlcv(raw, minutes, settings)
        counts = out.groupby(out.index.date).size()
        assert counts.max() == per_day, (minutes, counts.max(), per_day)
