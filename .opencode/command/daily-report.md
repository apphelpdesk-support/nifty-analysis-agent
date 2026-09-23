---
description: Generate today's Nifty research report (pipeline + interpretation). Loads the fetch-live-context skill to fill the Interpretation blocks.
---

Refresh the data if the last cached row in `data/historical/nifty.csv` is stale,
then run the full pipeline:

```
.venv\Scripts\python.exe scripts\update_data.py
.venv\Scripts\python.exe scripts\run_analysis.py
```

Read the generated report and backtest validation, then load the
`fetch-live-context` skill and follow it to fill the Interpretation blocks
(options OI/PCR, FII/DII, GIFT Nifty, overnight global markets and news) for
each scenario. Point the user at the report file.