"""Intraday loop health checks.

Guards the failure mode where a dead data feed looks healthy: the Fyers fetch
swallows network errors, so the loop must verify the archive actually advanced
before exporting and publishing it.
"""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import auto_intraday_loop as L

IST = L.IST
HEADER = "ts,open,high,low,close,volume\n"


def write_db(tmp_path, *rows, name="NSE_NIFTY50-INDEX.csv"):
    p = tmp_path / name
    p.write_text(HEADER + "".join(f"{r},1,1,1,1,1\n" for r in rows), encoding="utf-8")
    return p


def both(tmp_path, *rows):
    """Both published archives, so tests target the multi-symbol gate."""
    return [
        write_db(tmp_path, *rows, name="NSE_NIFTY50-INDEX.csv"),
        write_db(tmp_path, *rows, name="NSE_NIFTYBANK-INDEX.csv"),
    ]


def ist(y, mo, d, h, mi):
    # pytz requires localize(); tzinfo= would attach LMT (+05:53), not IST.
    return IST.localize(datetime(y, mo, d, h, mi))


# --- newest_fyers_bar -------------------------------------------------------

def test_newest_bar_reads_tail(tmp_path):
    p = write_db(tmp_path, "2026-09-28 09:15:00+05:30", "2026-09-28 15:25:00+05:30")
    assert L.newest_fyers_bar(p) == ist(2026, 9, 28, 15, 25)


def test_newest_bar_missing_file(tmp_path):
    assert L.newest_fyers_bar(tmp_path / "nope.csv") is None


def test_newest_bar_header_only(tmp_path):
    p = tmp_path / "NSE_NIFTY50-INDEX.csv"
    p.write_text(HEADER, encoding="utf-8")
    assert L.newest_fyers_bar(p) is None


def test_newest_bar_empty_file(tmp_path):
    p = tmp_path / "NSE_NIFTY50-INDEX.csv"
    p.write_text("", encoding="utf-8")
    assert L.newest_fyers_bar(p) is None


def test_newest_bar_malformed_timestamp(tmp_path):
    p = write_db(tmp_path, "not-a-timestamp")
    assert L.newest_fyers_bar(p) is None


def test_newest_bar_ignores_trailing_blank_lines(tmp_path):
    p = write_db(tmp_path, "2026-09-28 15:20:00+05:30")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("\n")
    assert L.newest_fyers_bar(p) == ist(2026, 9, 28, 15, 20)


# --- data_is_fresh ----------------------------------------------------------

def test_fresh_when_bar_is_two_minutes_old(tmp_path):
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 15:23:00+05:30"))
    assert ok is True
    assert "2 min old" in why


def test_stale_when_bar_is_thirty_minutes_old(tmp_path):
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 14:55:00+05:30"))
    assert ok is False
    assert "30 min old" in why


def test_fresh_at_the_tolerance_boundary(tmp_path):
    ok, _ = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 15:13:00+05:30"))
    assert ok is True


def test_stale_just_past_the_tolerance(tmp_path):
    ok, _ = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 15:12:00+05:30"))
    assert ok is False


def test_always_fresh_after_close(tmp_path):
    """The 15:31 final cycle must not self-block on a stale bar."""
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 15, 31), paths=both(tmp_path, "2026-09-28 09:15:00+05:30"))
    assert ok is True
    assert why == "market closed"


def test_missing_archive_is_not_fresh(tmp_path):
    paths = both(tmp_path, "2026-09-28 15:23:00+05:30")
    paths[1].unlink()
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 11, 0), paths=paths)
    assert ok is False
    assert "NIFTYBANK" in why
    assert "missing or empty" in why


def test_future_dated_bar_is_not_fresh(tmp_path):
    """Clock skew or a corrupt archive must not pin the check open."""
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 11, 0), paths=both(tmp_path, "2026-09-28 15:50:00+05:30"))
    assert ok is False
    assert "future" in why


def test_naive_timestamp_is_localised(tmp_path):
    ok, _ = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 15:23:00"))
    assert ok is True


def test_stale_second_symbol_blocks_whole_cycle(tmp_path):
    """NIFTY current but Bank Nifty stale must still block the push."""
    paths = [
        write_db(tmp_path, "2026-09-28 15:23:00+05:30", name="NSE_NIFTY50-INDEX.csv"),
        write_db(tmp_path, "2026-09-28 14:40:00+05:30", name="NSE_NIFTYBANK-INDEX.csv"),
    ]
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=paths)
    assert ok is False
    assert "NIFTYBANK" in why
    assert "45 min old" in why


def test_reason_names_each_symbol_when_all_fresh(tmp_path):
    ok, why = L.data_is_fresh(now=ist(2026, 9, 28, 15, 25), paths=both(tmp_path, "2026-09-28 15:23:00+05:30"))
    assert ok is True
    assert "NIFTY50" in why and "NIFTYBANK" in why


def test_published_archives_cover_both_feeds():
    """Guard the invariant that the gate tracks what the exporter publishes."""
    names = {p.stem for p in L.FYERS_ARCHIVES}
    assert names == {"NSE_NIFTY50-INDEX", "NSE_NIFTYBANK-INDEX"}


def test_after_close_boundary():
    assert L.after_close(ist(2026, 9, 28, 15, 30)) is False
    assert L.after_close(ist(2026, 9, 28, 15, 31)) is True
    assert L.after_close(ist(2026, 9, 28, 16, 0)) is True


# --- cycle gating -----------------------------------------------------------

@pytest.fixture
def spy(monkeypatch):
    """Drive cycle() with a scripted feed, and record what it actually did."""
    calls = []
    state = {
        "fetch_ok": True,
        "fresh": (True, "ok"),
        "closed": False,
    }

    def fake_run_step(cmd, desc):
        calls.append(desc)
        return state["fetch_ok"] if "update_data" in cmd[1] else True

    monkeypatch.setattr(L, "run_step", fake_run_step)
    monkeypatch.setattr(L, "git_commit_and_push", lambda: calls.append("PUSH"))
    monkeypatch.setattr(L, "clear_failures", lambda: None)
    monkeypatch.setattr(L, "record_failure", lambda r: calls.append("FAIL"))
    monkeypatch.setattr(L, "data_is_fresh", lambda *a, **k: state["fresh"])
    monkeypatch.setattr(L, "after_close", lambda *a, **k: state["closed"])
    return SimpleNamespace(calls=calls, state=state)


def test_cycle_blocks_export_and_push_when_stale(spy):
    spy.state["fresh"] = (False, "NIFTY50 stale")
    L.cycle()
    assert spy.calls == ["Fyers Live Data Fetch", "FAIL"]
    assert "PUSH" not in spy.calls
    assert not any("Export" in c for c in spy.calls)


def test_cycle_blocks_when_fetch_fails_but_data_looks_fresh(spy):
    """A failed fetch is itself disqualifying during market hours."""
    spy.state["fetch_ok"] = False
    L.cycle()
    assert "PUSH" not in spy.calls
    assert "FAIL" in spy.calls


def test_cycle_runs_full_pipeline_when_fresh(spy):
    L.cycle()
    assert spy.calls == ["Fyers Live Data Fetch", "Intraday WFO & JSON Export", "PUSH"]


def test_final_cycle_exports_even_if_fetch_fails(spy):
    """The 15:31 session export must not be lost to a failed last fetch."""
    spy.state["closed"] = True
    spy.state["fetch_ok"] = False
    L.cycle()
    assert "Intraday WFO & JSON Export" in spy.calls
    assert "PUSH" in spy.calls
    assert "FAIL" not in spy.calls


def test_stale_second_symbol_blocks_whole_cycle(spy):
    """NIFTY current but Bank Nifty stale must still block the push."""
    spy.state["fresh"] = (False, "NIFTY50 ok; NIFTYBANK: newest bar 14:40 is 45 min old")
    L.cycle()
    assert "PUSH" not in spy.calls
    assert "FAIL" in spy.calls


# --- failure tracking --------------------------------------------------------

def test_failure_counter_increments_and_resets(monkeypatch):
    monkeypatch.setattr(L, "_consecutive_failures", 0)
    monkeypatch.setattr(L, "_outage_started", None)
    L.record_failure("stale")
    assert L._consecutive_failures == 1
    L.record_failure("stale")
    assert L._consecutive_failures == 2
    L.clear_failures()
    assert L._consecutive_failures == 0
    assert L._outage_started is None


def test_clear_failures_is_silent_when_healthy(monkeypatch, capsys):
    monkeypatch.setattr(L, "_consecutive_failures", 0)
    monkeypatch.setattr(L, "_outage_started", None)
    L.clear_failures()
    assert "RECOVERED" not in capsys.readouterr().out


def test_recovery_is_reported_after_outage(monkeypatch, capsys):
    monkeypatch.setattr(L, "_consecutive_failures", 0)
    monkeypatch.setattr(L, "_outage_started", None)
    L.record_failure("stale")
    L.clear_failures()
    assert "RECOVERED" in capsys.readouterr().out


# --- fetch status plumbing --------------------------------------------------

def test_update_all_fyers_false_when_every_symbol_fails(monkeypatch):
    import core.data_intraday as di
    sys.modules.setdefault(
        "core.data_fyers",
        type("M", (), {"build_historical_database": staticmethod(lambda *a, **k: None)}),
    )
    monkeypatch.setattr(di, "update_from_fyers", lambda *a, **k: None)
    s = {"symbols": {"nifty": "^NSEI", "bank_nifty": "^NSEBANK"}}
    assert di.update_all_fyers(s) is False


def test_update_all_fyers_true_when_one_symbol_succeeds(monkeypatch):
    import core.data_intraday as di
    sys.modules.setdefault(
        "core.data_fyers",
        type("M", (), {"build_historical_database": staticmethod(lambda *a, **k: None)}),
    )
    seen = {"n": 0}

    def fake(name, symbol, settings, days=5):
        seen["n"] += 1
        return object() if seen["n"] == 1 else None

    monkeypatch.setattr(di, "update_from_fyers", fake)
    s = {"symbols": {"nifty": "^NSEI", "bank_nifty": "^NSEBANK"}}
    assert di.update_all_fyers(s) is True


def test_update_data_exits_nonzero_on_fyers_failure(monkeypatch):
    import core.data_intraday as di
    from scripts import update_data as ud
    monkeypatch.setattr(di, "update_all_fyers", lambda s: False)
    monkeypatch.setattr(sys, "argv", ["update_data.py", "--fyers"])
    with pytest.raises(SystemExit) as exc:
        ud.main()
    assert exc.value.code == 1


def test_update_data_exits_zero_on_fyers_success(monkeypatch):
    import core.data_intraday as di
    from scripts import update_data as ud
    monkeypatch.setattr(di, "update_all_fyers", lambda s: True)
    monkeypatch.setattr(sys, "argv", ["update_data.py", "--fyers"])
    with pytest.raises(SystemExit) as exc:
        ud.main()
    assert exc.value.code == 0
