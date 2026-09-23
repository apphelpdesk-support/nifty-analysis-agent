"""Zerodha Kite NIFTY 50 intraday backfill (2015-01-09 -> now, 5-minute bars).

Mint an access token once, then pull the full history:

    python scripts/backfill_intraday.py --login
    python scripts/backfill_intraday.py --backfill [--name nifty] [--verbose]

The index token (256265) and start date come from config/settings.json. Deep
bars have volume=0 (index has none on Kite); the free yfinance collector adds
recent bars WITH volume, so optionally run the collector afterwards:

    python scripts/update_data.py --intraday
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.settings as settings_mod
from core.providers import zerodha


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true", help="Mint Kite access token (one-time).")
    ap.add_argument("--backfill", action="store_true", help="Pull 5m archive from 2015 via Kite.")
    ap.add_argument("--name", default="nifty")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    settings = settings_mod.load_settings()
    if args.login:
        zerodha.login(settings)
        print("Login done. You can now run --backfill.")
        return
    if args.backfill:
        path = zerodha.backfill(settings, name=args.name, verbose=args.verbose)
        print(f"[kite] backfill archive -> {path}")
        return
    ap.print_help()


if __name__ == "__main__":
    main()