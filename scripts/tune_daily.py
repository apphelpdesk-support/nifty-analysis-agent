"""Daily-methodology sweep (Phase 1A).

Curated parameter grid over K, z-score lookback, feature subsets and weighting
variants, each scored by the same walk-forward no-lookahead gate. Produces
reports/backtest/tune-YYYY-MM-DD.html + a CSV of results.

Usage:
    python scripts/tune_daily.py [--quick]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.data as data
import core.settings as st
from backtest import backtest as bt

BASE_FEATURES = [
    "ret_1d", "ret_5d", "ret_20d",
    "rsi_14", "atr_pct", "gap_pct", "range_pct",
    "vol_20d", "dist_sma20", "dist_sma50", "dist_sma200", "macd_hist_pct",
]
EXTRA_FEATURES = ["dow_monday", "days_to_month_end", "expiry_zone"]
WEIGHT_SETS = {
    "default": None,  # settings baseline
    "vol_heavy": None,  # filled below from BASE weights
    "gap_heavy": None,  # filled below
}


def load_weight_sets(settings: dict) -> dict:
    base = dict(settings["analogues"]["weights"])
    vol = dict(base)
    gap = dict(base)
    for f in list(vol):
        if "vol" in f:
            vol[f] *= 1.8
    for f in list(gap):
        if "gap" in f or "atr" in f:
            gap[f] *= 1.8
    return {"default": base, "vol_heavy": vol, "gap_heavy": gap}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="smaller grid for a fast smoke run")
    args = ap.parse_args()

    settings = st.load_settings()
    df = data.load_series("nifty", settings)
    if df.empty:
        print("No data; run scripts/update_data.py first.")
        sys.exit(1)

    # single feature frame (all candidate columns present)
    full_frame = bt.prepare(settings, df)[0]
    frame = full_frame
    look_list = [250, 500, 750]
    k_list = [100, 200, 300]
    if args.quick:
        look_list, k_list = [500], [200]

    weights = load_weight_sets(settings)
    feat_sets = {"base": BASE_FEATURES, "base+cal": BASE_FEATURES + EXTRA_FEATURES}

    results = []
    for feat_label, feats in feat_sets.items():
        for look in look_list:
            z = bt.patterns.zscore_point_in_time(frame, feats, look)
            for k in k_list:
                for wlabel, w in weights.items():
                    wsub = {f: w.get(f, 1.0) for f in feats}
                    res = bt.evaluate(frame, z, feats, wsub, k, look, settings)
                    if not res["ok"]:
                        continue
                    results.append({
                        "feature_set": feat_label,
                        "k": k, "lookback": look, "weights": wlabel,
                        "hit_rate": round(res["hit_rate"], 4),
                        "always_up": round(res["always_up_acc"], 4),
                        "edge": round(res["edge"], 4),
                        "corr": round(res["corr"], 4),
                        "t_mean": round(res["t_mean"], 3),
                        "mae": round(res["mae"], 4),
                        "n_days": res["n_days"],
                        "n_strong": res["n_strong"],
                        "strong_mean": round(res["strong_mean_actual"], 4),
                        "n_weak": res["n_weak"],
                        "weak_mean": round(res["weak_mean_actual"], 4),
                    })
                    print(f"[tune] {feat_label} k={k} look={look} {wlabel}: "
                          f"hit={res['hit_rate']*100:.1f}% base=always_up={res['always_up_acc']*100:.1f}% "
                          f"edge={res['edge']*100:+.2f}% t={res['t_mean']:+.2f}")

    out = pd.DataFrame(results).sort_values("edge", ascending=False)
    out.insert(0, "rank", range(1, len(out) + 1))
    folder = st.rel(settings, "reports_dir") / settings["paths"]["backtest_reports_subdir"]
    folder.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = folder / f"tune-results-{date_str}.csv"
    out.to_csv(csv_path, index=False)

    best = out.iloc[0]
    html_path = write_tune_html(out, date_str, folder)
    print("\nBest variant:")
    for c in ["feature_set", "k", "lookback", "weights", "hit_rate", "edge", "t_mean", "corr"]:
        print(f"  {c}: {best[c]}")
    print(f"\nResults CSV -> {csv_path}")
    print(f"Results HTML -> {html_path}")


def write_tune_html(out: pd.DataFrame, date_str: str, folder: Path) -> Path:
    rows = ""
    for _, r in out.iterrows():
        rows += ("<tr><td>{r}</td><td>{f}</td><td>{k}</td><td>{l}</td><td>{w}</td>"
                 "<td>{h}</td><td>{a}</td><td>{e}</td><td>{c}</td><td>{t}</td><td>{m}</td></tr>").format(
            r=r["rank"], f=r["feature_set"], k=r["k"], l=r["lookback"], w=r["weights"],
            h=f"{r['hit_rate']*100:.1f}", a=f"{r['always_up']*100:.1f}",
            e=f"{r['edge']*100:+.2f}", c=r["corr"], t=f"{r['t_mean']:+.2f}", m=r["mae"])
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Tuning sweep</title>
<style>body{{font-family:'Segoe UI',Arial,sans-serif;margin:24px auto;max-width:1100px;}}
table{{border-collapse:collapse;width:100%;font-size:12px;}} td,th{{border:1px solid #ddd;padding:4px 8px;}}
th{{background:#f2f4f7;}} .top{{background:#e7f4e7;}}</style></head><body>
<h1>Daily methodology sweep</h1><p>Run: {date_str} &middot; sorted by edge (hit-rate &minus; always-up baseline)</p>
<table><tr><th>#</th><th>features</th><th>K</th><th>lookback</th><th>weights</th>
<th>hit%</th><th>always%</th><th>edge</th><th>corr</th><th>t_mean</th><th>MAE</th></tr>{rows}</table>
<p style="color:#666;font-size:11px;">No-lookahead walk-forward gate. Edge is the edge being tested; t_mean is the natural-significance gate ranking re-ranked after more data.</p>
</body></html>"""
    path = folder / f"tune-{date_str}.html"
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    main()