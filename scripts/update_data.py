"""Refresh historical + daily Nifty data.

Usage:
    python scripts/update_data.py                 # everything (daily)
    python scripts/update_data.py --intraday      # recent intraday (60d, free)
    python scripts/update_data.py --symbols nifty # just one daily series
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.data as data
import core.settings as st
from core import data_intraday


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh the historical Nifty dataset")
    ap.add_argument(
        "--symbols",
        choices=["all", "nifty", "bank_nifty", "india_vix"],
        default="all",
    )
    ap.add_argument(
        "--intraday",
        action="store_true",
        help="Refresh the 60-day 5-minute archive via the free yfinance collector",
    )
    ap.add_argument(
        "--fyers",
        action="store_true",
        help="Refresh live Nifty data directly from the Fyers API (zero delay)",
    )
    args = ap.parse_args()

    settings = st.load_settings()
    if args.fyers:
        data_intraday.update_all_fyers(settings)
        return

    if args.intraday:
        data_intraday.update_all_free(settings)
        return

    if args.symbols == "all":
        data.update_all(settings)
    else:
        sym = settings["symbols"][args.symbols]
        data.update_history(args.symbols, sym, settings)
    data.save_daily_snapshots(settings)
    print("Done. Data is cached under data/historical/.")


if __name__ == "__main__":
    main()