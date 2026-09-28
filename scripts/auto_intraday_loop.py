"""Automated intraday runner for market hours (09:15 to 15:30 IST).

Runs every 5 minutes:
1. Fetches latest candles via Fyers (or fallback)
2. Runs intraday WFO and exports 5m, 15m, 30m, 60m JSON feeds
3. Commits and pushes intraday_*.json to GitHub Pages
4. Automatically terminates after market close at 15:31 IST.
"""
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import pytz

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

IST = pytz.timezone("Asia/Kolkata")
PYTHON_EXE = sys.executable

FYERS_DB_DIR = ROOT_DIR / "data" / "fyers_db" / "5"
# Every 5m archive the exporter publishes (see export_intraday.py). The gate
# must cover all of them: a NIFTY-ok / Bank-Nifty-fail cycle would otherwise
# republish stale Bank Nifty behind a passing exit code.
FYERS_ARCHIVES = [
    FYERS_DB_DIR / "NSE_NIFTY50-INDEX.csv",
    FYERS_DB_DIR / "NSE_NIFTYBANK-INDEX.csv",
]
MARKET_CLOSE = (15, 31)
# Fyers labels bars by their start, so the newest bar is normally 0-5 min old.
# Allow ~2.4 bars before calling the feed stale.
MAX_BAR_AGE_MIN = 12

_consecutive_failures = 0
_outage_started = None

def log(msg: str):
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} IST] {msg}", flush=True)

def after_close(now=None) -> bool:
    now = now or datetime.now(IST)
    return (now.hour, now.minute) >= MARKET_CLOSE

def newest_fyers_bar(path):
    """Newest bar timestamp in a Fyers archive, or None if unreadable.

    Tails the file rather than loading it: the archive is rewritten by the
    fetch step and this runs every cycle.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            last = ""
            for line in fh:
                if line.strip():
                    last = line
        if not last or last.lower().startswith("ts,"):
            return None
        return datetime.fromisoformat(last.split(",")[0].strip())
    except (OSError, ValueError, IndexError):
        return None

def _archive_is_fresh(path, now, max_age_min):
    """Freshness of a single archive. Returns (fresh, reason)."""
    label = path.stem.replace("NSE_", "").replace("-INDEX", "")
    ts = newest_fyers_bar(path)
    if ts is None:
        return False, f"{label}: archive missing or empty"
    if ts.tzinfo is None:
        # pytz needs localize(), not replace(tzinfo=...): the latter attaches
        # the zone's LMT offset (+05:53) instead of IST (+05:30).
        ts = IST.localize(ts)
    age = (now - ts).total_seconds() / 60.0
    if age < -max_age_min:
        # Future-dated bar: clock skew or a corrupt archive. Reporting this as
        # fresh would pin the check open forever.
        return False, f"{label}: newest bar {ts:%H:%M} is {-age:.0f} min in the future"
    if age > max_age_min:
        return False, f"{label}: newest bar {ts:%H:%M} is {age:.0f} min old (limit {max_age_min})"
    return True, f"{label} {ts:%H:%M} ({age:.0f} min old)"

def data_is_fresh(now=None, max_age_min=MAX_BAR_AGE_MIN, paths=None):
    """Is every published archive current enough to export and push?

    Returns (fresh, reason). After the close the final cycle must not block,
    so staleness is only judged during market hours. Stateless, so it still
    works after a restart.
    """
    now = now or datetime.now(IST)
    if after_close(now):
        return True, "market closed"
    paths = FYERS_ARCHIVES if paths is None else list(paths)
    results = [_archive_is_fresh(p, now, max_age_min) for p in paths]
    stale = [why for ok, why in results if not ok]
    if stale:
        return False, "; ".join(stale)
    return True, ", ".join(why for _, why in results)

def record_failure(reason: str):
    global _consecutive_failures, _outage_started
    now = datetime.now(IST)
    if _consecutive_failures == 0:
        _outage_started = now
    _consecutive_failures += 1
    log(f"ALERT: {reason} (consecutive failures: {_consecutive_failures})")
    if _consecutive_failures == 3:
        log(f"ALERT: data feed has been stale for 3 consecutive cycles "
            f"(~15 min). Dashboard will keep showing the last good data.")

def clear_failures():
    global _consecutive_failures, _outage_started
    if _consecutive_failures:
        dur = datetime.now(IST) - _outage_started
        mins = int(dur.total_seconds() // 60)
        log(f"RECOVERED: data feed back to normal after {mins} min "
            f"({_consecutive_failures} failed cycles). Resuming export.")
    _consecutive_failures = 0
    _outage_started = None

def run_step(cmd_args, desc):
    log(f"Running: {desc}...")
    try:
        res = subprocess.run(
            cmd_args,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=180
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            log(f"Warning in {desc}: {err}")
            return False
        return True
    except Exception as e:
        log(f"Error in {desc}: {e}")
        return False

def git_commit_and_push():
    diff_check = subprocess.run(
        ["git", "status", "--porcelain", "intraday_*.json"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True
    )
    if not diff_check.stdout.strip():
        log("No changes in intraday JSON files. Skipping git push.")
        return

    log("Staging intraday JSON changes...")
    subprocess.run(["git", "add", "intraday_*.json"], cwd=str(ROOT_DIR), check=False)
    
    commit_msg = f"Auto intraday update ({datetime.now(IST).strftime('%H:%M IST')})"
    commit_res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(ROOT_DIR), capture_output=True, text=True)
    if commit_res.returncode != 0 and "nothing to commit" in commit_res.stdout:
        log("Nothing to commit.")
        return

    log("Pushing to GitHub Pages (origin main)...")
    push_res = subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT_DIR), capture_output=True, text=True)
    if push_res.returncode == 0:
        log("Push successful!")
    else:
        log(f"Push failed, attempting pull --rebase: {push_res.stderr.strip()}")
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=str(ROOT_DIR), capture_output=True, text=True)
        push_res2 = subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT_DIR), capture_output=True, text=True)
        if push_res2.returncode == 0:
            log("Push successful after rebase!")
        else:
            log(f"Push retry failed (will retry next cycle): {push_res2.stderr.strip()}")

def cycle():
    log("=== Starting Intraday Sync Cycle ===")
    # 1. Update data via Fyers (and YF fallback)
    fetched = run_step([PYTHON_EXE, "scripts/update_data.py", "--fyers"], "Fyers Live Data Fetch")

    # 2. Gate on the data actually being current. The fetch swallows network
    #    errors, so a non-zero exit alone is not proof of failure -- and a zero
    #    exit is not proof of success either. Check the archive itself.
    fresh, reason = data_is_fresh()
    # The closing cycle is exempt: the archive already holds the full session
    # and data_is_fresh() always passes after the close, so a failed last fetch
    # must not cost us the final session export.
    final_cycle = after_close()

    if not final_cycle and not (fetched and fresh):
        if fetched and not fresh:
            log("Fyers fetch reported success but the archive is not current.")
        log("Skipping export and push to avoid publishing stale data.")
        record_failure(reason)
        log("=== Cycle Aborted ===")
        return

    clear_failures()
    # 3. Export intraday
    run_step([PYTHON_EXE, "scripts/export_intraday.py"], "Intraday WFO & JSON Export")
    # 4. Push to git
    git_commit_and_push()
    log("=== Cycle Complete ===")

def main():
    log("Starting Intraday Automation Loop until 15:31 IST...")

    while True:
        now = datetime.now(IST)

        # Stop condition: past 15:31 IST
        if after_close(now):
            log("Market hours ended (>= 15:31 IST). Running final session export...")
            cycle()
            log("Final session export complete. Exiting auto loop.")
            break

        cycle()

        # Re-check time after cycle runs
        now = datetime.now(IST)
        if after_close(now):
            log("Market hours ended. Exiting auto loop.")
            break
            
        # Calculate seconds until next 5-minute mark + 10s buffer (:00:10, :05:10, :10:10, etc.)
        current_minute = now.minute
        current_second = now.second
        next_minute = (current_minute // 5 + 1) * 5
        seconds_to_wait = (next_minute - current_minute) * 60 - current_second + 10
        if seconds_to_wait < 10:
            seconds_to_wait += 300
            
        target_time = now + timedelta(seconds=seconds_to_wait)
        log(f"Sleeping {int(seconds_to_wait)}s until next bar at {target_time.strftime('%H:%M:%S IST')}...")
        time.sleep(seconds_to_wait)

if __name__ == "__main__":
    main()
