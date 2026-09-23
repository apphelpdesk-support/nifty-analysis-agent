---
name: fetch-live-context
description: Use when the Nifty Analyst report needs live interpretation inputs — FII/DII flows, GIFT Nifty pre-open, options OI/PCR/IV, India VIX cross-check, overnight global markets or macro news — or when the daily report should have its Interpretation blocks filled in. Triggers on "interpretation", "FII/DII", "GIFT Nifty", "options OI", "fill scenario blocks".
---

# Fetch live context for the report's Interpretation blocks

The statistical engine (`scripts/run_analysis.py`) already computes the
historical/technical facts. Your job is to fetch the LIVE, non-cached inputs and
place them in the *Interpretation* blocks of the generated daily report
(`reports/daily/daily-<date>.html`) — keeping them clearly separate from the
statistical tables above them.

## Facts to gather (websearch tool)

1. **FII / DII provisional net buys (₹ crore)** — search for
   "FII DII provisional net investment today". Always label the value as
   *provisional* with the date and source.
2. **GIFT Nifty** — latest/pre-open level vs the NIFTY close → an overnight gap
   signal (+ high = risk-on open). Label source + timestamp.
3. **Options OI / PCR** — if you can obtain clean NSE index-option OI (best
   effort; NSE may block bots):
   - write a tidy CSV to `data/options/<YYYY-MM-DD>.csv` with columns
     `date,index,ce_oi,pe_oi,pcr,atm_strike,atm_iv` and then re-run
     `.venv\Scripts\python.exe scripts\run_analysis.py --no-backtest` so the
     PCR line appears under the Market/global context section.
   - if you cannot obtain OI, say so in the Interpretation block; never invent
     OI numbers.
4. **India VIX** — already in the report from the cached series; only add a
   cross-check if material (e.g., a spike since the cache row).
5. **Overnight global / macro headlines** — 1-2 sentences max per scenario,
   sourced from the search results (US indices, 10Y, DXY, crude, gold are
   already tabled from cache; don't repeat them).

## Rules

- **Separate evidence from interpretation.** Statistical tables/sections must
  not be altered. Only fill the `Interpretation` blocks (the `<div class="interp">`
  paragraphs in the Scenarios section) and the trailing note.
- **Never fabricate numbers.** Every live figure needs a source + date/time; if
  you only have a stale number, say "as of <date>".
- **Consistency check:** interpretation must not contradict the reported
  statistics without explanation (e.g., "conflicting signal: FII selling but
  cohort is bullish").
- Edit the generated HTML with the Edit tool (the placeholder strings are
  `Filled by the Nifty Analyst agent...`). Then re-verify the file opens cleanly.