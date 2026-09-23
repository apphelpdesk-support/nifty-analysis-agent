---
name: fetch-nifty
description: Use when the Nifty Analyst workspace needs historical market data refreshed or updated. Triggers on "update data", "refresh data", "download nifty data", "stale data", running the daily pipeline for the first time.
---

# Fetch / refresh Nifty historical data

Refresh the cached daily OHLCV series used by the analogue engine.

1. Run the project venv python (not the system python):
   ```
   .venv\Scripts\python.exe scripts\update_data.py
   ```
   Optional: restrict to one series with `--symbols nifty|bank_nifty|india_vix`.
2. Verify the cache updated: `data/historical/nifty.csv` should now end at the
   most recent trading day.
3. Confirm the latest-row snapshot in `data/daily/nifty.csv` matches.

Notes:
- The download is incremental — it resumes from the last cached row, so
  re-running is cheap and idempotent.
- If yfinance is down or the symbol returns empty rows, the script prints a
  warning and keeps the existing cache; do not fabricate prices.
- Global series (US indices, DXY, INR, crude, gold) are fetched too; failures
  there are non-fatal.