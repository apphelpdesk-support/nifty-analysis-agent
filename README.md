# Nifty Analyst

**📖 [Read the Institutional Edge Dashboard Walkthrough](dashboard_walkthrough.md)** for a complete layman's guide on how to trade using the quantitative dashboard and execution safeguards.

Python research & backtesting system for NIFTY 50 daily analysis, built around
**historical-analogue matching**: find the most similar historical days to
today's technical setup, then read what happened on the following day.

**Phase 1 = core historical methodology (no live inputs).**
Live data (options OI, GIFT Nifty, FII/DII, overnight markets) is Phase 2 and is
only added after the Phase-1 backtest shows the methodology has historical value.

## Design rules

- **No lookahead.** Features at day D use only data up to the close of D.
  Analogues are drawn strictly from days before D. Z-scoring uses a trailing
  lookback window, never full-sample statistics.
- **Historical/statistical evidence is separated from interpretation.** The
  statistical modules only output distributions. Assessment/opinion is written
  by the orchestrating agent in clearly-labelled "Interpretation" blocks.
- **Everything is configurable** in `config/settings.json` (symbols, K, lookback,
  feature weights, thresholds).

## Layout

```
data/historical/   cached daily OHLCV CSV per series
data/daily/        latest-row snapshots
data/options/      (Phase 2) options OI snapshots
analysis/          technical.py, patterns.py (analogues + outcomes), report.py
backtest/          walk-forward no-lookahead validation
reports/daily/     daily research reports (HTML + PDF)
reports/backtest/  backtest validation report
config/            settings.json
scripts/           update_data.py, run_analysis.py
core/              settings loader + data pipeline
app.py             Streamlit explorer
```

## Setup

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows
pip install -r requirements.txt
```

## Usage

```
python scripts/update_data.py           # download/refresh NIFTY + global data
python scripts/run_analysis.py          # full pipeline -> reports/daily/*.html/.pdf
python scripts/run_analysis.py --no-backtest

streamlit run app.py                    # interactive explorer (plays with MA, K, lookback)
```

## Reading the report

- **Similar historical setups:** N · **Next day positive:** X · **Negative:** Y · **Median next-day move:** +Z% · **Historical range P5–P95.**
- Scenario bands (Bullish / Neutral / Bearish) are derived purely from the analogue
  next-day distribution; the agent fills the *Interpretation* blocks with news,
  internals and overnight context in Phase 2.
- **Backtest validation:** months of out-of-sample, walk-forward runs comparing
  analogue predictions against an always-up baseline. Edge shows up as hit-rate
  above baseline and a material `t_mean`.

This is research software, not investment advice.