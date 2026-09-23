"""Phase-1B tuning sweep for the intraday analogue engine (mirrors tune_daily).

Sweeps K x lookback x weight-set x feature-set on the 5m archive's walk-forward
gate (edge = direction hit-rate minus the always-rest-up baseline, the natural
intraday baseline), plus corr and MAE for magnitude skill.

Usage:
    python scripts/tune_intraday.py [--quick] [--tf 5]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

import core.data as data
import core.settings as settings_mod
from analysis import intraday, patterns, report
from backtest import intraday as bt_intraday
from core import session

WEIGHT_SETS = {
    "default": {},
    "micro_heavy": {"bar_no": 1.0, "time_in_session": 0.8, "ret_1bar": 1.0, "ret_6bar": 0.9},
    "rsi_heavy": {"rsi_14": 1.6, "dist_vwap": 1.0, "vol_14": 0.9, "atr_pct": 0.8},
}
FEATURE_SETS = {
    "full": None,
    "no_calendar": ["dow_monday", "days_to_month_end", "expiry_zone"],
    "no_context": ["daily_vol_z", "daily_ret_prev"],
}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--tf", type=int, default=5)
    args = ap.parse_args(argv)

    settings = settings_mod.load_settings()
    t0 = time.time()
    bars = session.archive_bars("nifty", args.tf, settings)
    daily = data.load_series("nifty", settings)
    frame = intraday.build_features(bars, daily, settings)

    base_weights = settings["intraday"]["weights"]
    feats_all = settings["intraday"]["features"]

    if args.quick:
        ks = [100, 200]
        looks = [250, 500]
    else:
        ks = [50, 100, 200]
        looks = [250, 500, 750]

    zcache = {}
    results = []
    n = len(frame)
    for look in looks:
        zcache[look] = patterns.zscore_point_in_time(frame, feats_all, look)

    for k in ks:
        for look in looks:
            for w_name, w_extra in WEIGHT_SETS.items():
                for fs_name, drop in FEATURE_SETS.items():
                    feats = [f for f in feats_all if f not in (drop or [])]
                    weights = dict(base_weights)
                    weights.update(w_extra)
                    res = bt_intraday.backtest_bars(
                        frame, settings, feats, weights, k=k, lookback=look,
                        target=settings["intraday"]["primary_target"],
                    )
                    results.append({
                        "k": k, "lookback": look, "weights": w_name, "features": fs_name,
                        "bars": res.get("n_days", 0),
                        "hit": res.get("hit_rate", np.nan) * 100,
                        "base": res.get("always_up_acc", np.nan) * 100,
                        "edge": res.get("edge", np.nan),
                        "corr": res.get("corr", np.nan),
                        "mae": res.get("mae", np.nan),
                    })
                    status = "+" if res.get("edge", -1) > 0 else " "
                    print(f"[{status}] k={k:>3} look={look:>4} {w_name:>12} {fs_name:>11}  "
                          f"hit={results[-1]['hit']:5.1f}% base={results[-1]['base']:5.1f}% "
                          f"edge={results[-1]['edge']:+6.2f}pp corr={results[-1]['corr']:+.3f}")

    df = pd.DataFrame(results).sort_values("edge", ascending=False)
    print()
    print("TOP 10 BY EDGE")
    print(df.head(10).to_string(index=False))
    print()
    print("TOP 5 BY CORR (magnitude skill)")
    print(df.sort_values("corr", ascending=False).head(5).to_string(index=False))

    # write sweep artifacts
    folder = settings_mod.rel(settings, "reports_dir") / settings["paths"]["backtest_reports_subdir"]
    folder.mkdir(parents=True, exist_ok=True)
    df.to_csv(folder / f"tune-intraday-{args.tf}m-results.csv", index=False)
    best = df.iloc[0]
    html = f"""<html><head><meta charset="utf-8"><title>Intraday tuning sweep</title></head><body>
<h1>Intraday ({args.tf}m) tuning sweep — {len(df)} variants, took {time.time()-t0:.0f}s</h1>
<p>Best: k={best['k']}, lookback={int(best['lookback'])}, weights={best['weights']}, features={best['features']} →
edge {best['edge']:+.2f}pp (hit {best['hit']:.1f}% vs base {best['base']:.1f}%), corr {best['corr']:+.3f}, MAE {best['mae']:.2f}%</p>
{df.round(3).to_html(index=False)}
</body></html>"""
    (folder / f"tune-intraday-{args.tf}m.html").write_text(html, encoding="utf-8")
    print(f"\nSweep ran in {time.time()-t0:.0f}s; artifacts in reports/backtest/tune-intraday-{args.tf}m.*")


if __name__ == "__main__":
    main()