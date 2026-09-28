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

def log(msg: str):
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} IST] {msg}", flush=True)

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
    run_step([PYTHON_EXE, "scripts/update_data.py", "--fyers"], "Fyers Live Data Fetch")
    # 2. Export intraday
    run_step([PYTHON_EXE, "scripts/export_intraday.py"], "Intraday WFO & JSON Export")
    # 3. Push to git
    git_commit_and_push()
    log("=== Cycle Complete ===")

def main():
    log("Starting Intraday Automation Loop until 15:31 IST...")
    
    while True:
        now = datetime.now(IST)
        
        # Stop condition: past 15:31 IST
        if (now.hour > 15) or (now.hour == 15 and now.minute >= 31):
            log("Market hours ended (>= 15:31 IST). Running final session export...")
            cycle()
            log("Final session export complete. Exiting auto loop.")
            break
            
        cycle()
        
        # Re-check time after cycle runs
        now = datetime.now(IST)
        if (now.hour > 15) or (now.hour == 15 and now.minute >= 31):
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
