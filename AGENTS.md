# Nifty Analyst project rules

This workspace is a Python research system for NIFTY 50 daily analysis based on
historical-analogue matching. It is NOT a web app.

## Invariants (do not break)

- **No lookahead.** Features/analogues/backtest must never use future data.
  Point-in-time conventions live in `analysis/patterns.py` — keep z-scoring on
  trailing windows and analogues strictly before the target day.
- **Evidence separated from interpretation.** Statistical output (analogue
  distributions, MAD/MAF, percentiles, backtest metrics) is produced by
  `analysis/` and `backtest/` modules. Human-style assessment, news, FII/DII,
  options OI and overnight factors belong in clearly labelled *Interpretation*
  blocks, written by the agent, not mixed into the statistical tables.
- **Config-first.** Change parameters in `config/settings.json`, not in code.

## Standard workflows

- Refresh data: `python scripts/update_data.py` (run the venv python).
- Generate report: `python scripts/run_analysis.py`.
- Explorer: `streamlit run app.py` (timeframe switch in sidebar).
- Intraday refresh (free 60d, 5m): `python scripts/update_data.py --intraday`.
- Intraday report: `python scripts/run_intraday.py [--tf 5|15|30|60]`.
- Intraday deep backfill (2015+, Zerodha Kite): `python scripts/backfill_intraday.py --login` then `--backfill`.
- Data cache lives in `data/historical/*.csv` (daily), `data/intraday/5m/*.csv` (canonical 5m archive; 15/30/60 derived by session-aware resample, so only 5m is stored).

## Intraday invariants

- Bar features are point-in-time; forward outcomes are same-session only, and
  session-final bars are excluded from analogue candidates (no valid rest-of-session).
- Session = 09:15-15:30 IST; resampling anchors at 09:15 (`origin="start"`) so
  bars never bridge sessions. Pre-open rows (e.g. the Fyers 09:05/09:10 bars)
  are filtered out by `core.session.filter_session`.
- The raw 5m cap (`intraday.max_raw_bars_5m`) is applied **before** resampling,
  so 5/15/30/60m all cover the same calendar span.
- Deep Kite index bars have volume=0 (index has none); volume context uses the
  lagged daily aggregate. NOTE: the 60d yfinance collector has been observed to
  carry volume=0 on ~99% of bars, which contradicts an earlier version of this
  line — treat yfinance bar volume as unreliable.

## Intraday automation

- `scripts/auto_intraday_loop.py` runs every 5 min in market hours and **must be
  launched manually each trading day** — there is no scheduled task for it. It
  self-terminates at 15:31 IST after a final session export.
- The loop gates on data freshness, not exit codes: the Fyers fetch swallows
  network errors, so before exporting/pushing it verifies the newest bar in
  **every** published 5m archive (`FYERS_ARCHIVES` in the script) is within
  12 min. Gating on NIFTY alone would republish a stale Bank Nifty. On stale
  data it logs `ALERT`, skips the export and push, and reports `RECOVERED`
  when the feed returns. **Consequence: during a feed outage the dashboard
  freezes rather than republishing stale data, and the commit log gaps.** That
  is intended.
- The closing 15:31 cycle is exempt from the gate: the archive already holds
  the full session, so a failed final fetch must not cost the session export.



## Working environment

- Use the project venv: `.venv\Scripts\python.exe`.
- Install new deps with `pip install <pkg>` and add to `requirements.txt`.
- After downloading data or generating reports, do not commit the generated
  CSVs/HTML/PDF (they are gitignored).

## Report format

Daily report sections: technical setup, analogue + next-day outcome statistics,
current-vs-analogue divergence, scenarios. Each scenario block separates
**Historical/Statistical evidence** from **Interpretation**.