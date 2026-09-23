"""Full Phase-1 analysis pipeline -> reports/daily/*.html + .pdf plus the
backtest validation report.

Usage:
    python scripts/run_analysis.py          # full pipeline incl. backtest
    python scripts/run_analysis.py --no-backtest   # skip walk-forward validation
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.data as data
import core.settings as st
from analysis import market_context, options, patterns, report
from backtest import backtest as backtest_mod


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the daily Nifty research report")
    ap.add_argument("--no-backtest", action="store_true")
    args = ap.parse_args()

    settings = st.load_settings()
    df = data.load_series("nifty", settings)
    if df.empty:
        print("No cached data. Run:  python scripts/update_data.py")
        sys.exit(1)

    analog_cfg = settings["analogues"]
    frame = patterns.build_features(df, settings)
    features = analog_cfg["features"]
    weights = analog_cfg["weights"]
    k, look = analog_cfg["k"], analog_cfg["standardize_lookback"]

    z = patterns.zscore_point_in_time(frame, features, look)
    target_pos = len(frame) - 1
    idxs, dists = patterns.find_analogues(frame, z, features, weights, target_pos, k, look)
    cohort = frame.iloc[idxs].copy()
    cohort["distance"] = dists
    stats = patterns.outcome_stats(cohort)
    stats["analogue_count"] = len(idxs)
    divergence = patterns.divergence(frame, cohort, features)
    scenarios = patterns.scenarios(stats, settings["sentiment"])

    asof = frame.index[-1]
    ctx = {
        "settings": settings,
        "asof": asof,
        "frame": frame,
        "analogue_positions": idxs,
        "cohort": cohort,
        "stats": stats,
        "divergence": divergence,
        "scenarios": scenarios,
        "context": market_context.context_snapshot(settings),
        "options": options.snapshot(settings),
    }

    backtest_res = None
    if not args.no_backtest:
        backtest_res = backtest_mod.run(settings, df)
        ctx["backtest"] = backtest_res

    html_path, pdf_path = report.write_full_report(ctx, settings)
    print(f"\nReport written:\n  HTML -> {html_path}\n  PDF  -> {pdf_path}")

    if backtest_res:
        bhtml, _ = report.write_backtest_report(backtest_res, ctx, settings)
        print(f"  Backtest validation -> {bhtml}")

    _console_summary(ctx, backtest_res)


def _console_summary(ctx, backtest_res) -> None:
    stats = ctx["stats"]
    scen = ctx["scenarios"]
    d = stats["direction"]
    print("\n" + "=" * 62)
    print("NIFTY ANALYST - daily summary")
    print("=" * 62)
    print(f"As-of: {ctx['asof']:%Y-%m-%d}")
    print(f"Close: {ctx['frame']['close'].iloc[-1]:,.1f}  RSI: {ctx['frame']['rsi_14'].iloc[-1]:.1f}")
    print(f"Similar historical setups: {stats['analogue_count']}")
    print(f"Next day positive: {d['up']}  |  negative: {d['down']}  |  prob up: {d['prob_up']*100:.1f}%")
    nxt = stats["nxt_ret"]
    print(f"Median next-day move: {nxt.get('median', float('nan')):+.2f}%  |  range P5-P95: {nxt.get('p5', float('nan')):+.2f}% to {nxt.get('p95', float('nan')):+.2f}%")
    print(f"Statistical bias: {scen['bias']}  |  Bull target P75 {scen['bullish_scenario']['target_median_ret']:+.2f}%  |  Bear target P25 {scen['bearish_scenario']['target_median_ret']:+.2f}%")
    vix = ctx.get("context", {}).get("vix")
    if vix:
        print(f"India VIX: {vix['level']} ({vix['chg_1d_pct']:+.1f}% d/d)  regime {vix['regime']}  1y pctile {vix['pctile_1y']:.0f}%")
    o = ctx.get("options")
    if o and o.get("available"):
        print(f"Options PCR: {o['last']} ({o['regime']})  asof {o['asof']:%Y-%m-%d}")
    else:
        print("Options OI data: not cached yet (agent fetches via fetch-nifty skill)")
    if backtest_res and backtest_res["ok"]:
        print("-" * 62)
        print("Backtest (no-lookahead, walk-forward):")
        print(f"  days={backtest_res['n_days']}  hit_rate={backtest_res['hit_rate']*100:.1f}%  always_up_base={backtest_res['always_up_acc']*100:.1f}%  edge={backtest_res['edge']*100:+.2f}pp  corr={backtest_res['corr']:.3f}  t_mean={backtest_res['t_mean']:.2f}")
        print(f"  strong-bull days: n={backtest_res['n_strong']} actual mean {backtest_res['strong_mean_actual']:+.3f}% | weak days: n={backtest_res['n_weak']} actual mean {backtest_res['weak_mean_actual']:+.3f}%")
    print("=" * 62)


if __name__ == "__main__":
    main()