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
  bars never bridge sessions.
- Deep Kite index bars have volume=0 (index has none); volume context uses the
  lagged daily aggregate. The 60d yfinance collector carries real bar volume.

## Working environment

- Use the project venv: `.venv\Scripts\python.exe`.
- Install new deps with `pip install <pkg>` and add to `requirements.txt`.
- After downloading data or generating reports, do not commit the generated
  CSVs/HTML/PDF (they are gitignored).

## Report format

Daily report sections: technical setup, analogue + next-day outcome statistics,
current-vs-analogue divergence, scenarios. Each scenario block separates
**Historical/Statistical evidence** from **Interpretation**.