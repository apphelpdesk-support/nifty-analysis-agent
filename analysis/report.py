"""Report generation: daily research report (HTML + PDF) and backtest
validation report. Matplotlib PdfPages is used for PDF so there is no system
GTK/weasyprint dependency on Windows."""
import base64
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import core.settings as settings_mod

STAT_BLUE = "#1f6feb"
POS = "#0a8f3c"
NEG = "#d13438"

plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "axes.grid": True, "grid.alpha": 0.3})


# ---------------------------------------------------------------- charts ----
def _fig_to_png(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def price_chart(frame, analogue_positions, ma_periods) -> BytesIO:
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(frame.index, frame["close"], label="Close", color="#222", lw=1.1)
    for n in ma_periods:
        ax.plot(frame.index, frame[f"sma_{n}"], label=f"SMA {n}", lw=0.9)
    if analogue_positions:
        pts = frame.iloc[analogue_positions]
        ax.scatter(pts.index, pts["close"], color=STAT_BLUE, s=14, alpha=0.55, label=f"Top analogues ({len(pts)})")
    ax.scatter([frame.index[-1]], [frame["close"].iloc[-1]], marker="*", s=160, color=NEG, zorder=5, label="Today")
    ax.set_title("NIFTY 50 with similar-day analogues")
    ax.legend(loc="upper left", ncol=3, fontsize=8)
    ax.set_ylabel("Index level")
    return _fig_to_png(fig)


def indicator_chart(frame) -> BytesIO:
    fig, axes = plt.subplots(
        3, 1, figsize=(11, 7.5), sharex=False,
        gridspec_kw={"height_ratios": [1.6, 1.1, 1.0]},
    )
    ax = axes[0]
    ax.plot(frame.index, frame["rsi_14"], color="#7a5af8", lw=1)
    ax.axhline(70, color=NEG, lw=0.8, ls="--")
    ax.axhline(30, color=POS, lw=0.8, ls="--")
    ax.set_ylim(0, 100)
    ax.set_title("RSI(14)")

    ax = axes[1]
    ax.plot(frame.index, frame["macd"], label="MACD", color=STAT_BLUE, lw=1)
    ax.plot(frame.index, frame["macd_signal"], label="Signal", color="#e06c00", lw=1)
    ax.bar(frame.index, frame["macd_hist"], color=np.where(frame["macd_hist"] >= 0, POS, NEG), alpha=0.6, width=1)
    ax.set_title("MACD(12,26,9)")
    ax.legend(loc="upper left", fontsize=8)

    ax = axes[2]
    ax.plot(frame.index, frame["vol_20d"], color="#8a8f98", lw=1, label="20d real. vol %")
    ax.set_title("20-day realised volatility (annualized %)")
    fig.tight_layout()
    return _fig_to_png(fig)


def outcome_histogram(ctx) -> BytesIO:
    stats = ctx["stats"]["nxt_ret"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.hist(ctx["cohort"]["nxt_ret"].dropna(), bins=36, color="#aec8f5", edgecolor="#5b8dd9")
    ax.axvline(0, color="#333", lw=1)
    for p, c, ls in [("p5", "#888", "--"), ("p25", NEG, ":"), ("median", "#222", "-"), ("p75", POS, ":"), ("p95", "#888", "--")]:
        if p in stats:
            ax.axvline(stats[p], color=c, ls=ls, lw=1)
    ax.set_title(f"Next-day return distribution of {stats['count']} analogous days (ret %)")
    ax.set_xlabel("Next-day close return (%)")
    ax.set_ylabel("Frequency")
    fig.tight_layout()
    return _fig_to_png(fig)


def mad_maf_chart(ctx) -> BytesIO:
    r = pd.DataFrame(
        {
            "nxt_mad": ctx["cohort"]["nxt_mad"].dropna(),
            "nxt_maf": ctx["cohort"]["nxt_maf"].dropna(),
        }
    )
    fig, ax = plt.subplots(figsize=(7, 3.8))
    summary = r[["nxt_mad", "nxt_maf"]].mean().round(2)
    ax.bar(["MAD (max adverse exc.)", "MAF (max favourable exc.)"], summary.values,
           color=[NEG, POS], alpha=0.85)
    axes2 = ax.twinx()
    axes2.scatter(["MAD (max adverse exc.)", "MAF (max favourable exc.)"],
                  [r["nxt_mad"].median(), r["nxt_maf"].median()], color="#222", marker="x", s=60, label="median")
    axes2.set_ylabel("median (%)")
    axes2.legend(loc="upper right", fontsize=8)
    ax.set_ylabel("mean next-day excursion vs prior close (%)")
    ax.set_title("Next-day maximum adverse / favourable excursion")
    fig.tight_layout()
    return _fig_to_png(fig)


# ---------------------------------------------------------------- html -----
def _img_tag(key, images: dict) -> str:
    return f'<img src="data:image/png;base64,{base64.b64encode(images[key].getvalue()).decode()}" style="max-width:100%;height:auto">'


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:.{nd}f}"


def render_html(ctx: dict, settings: dict, images: dict) -> str:
    stats = ctx["stats"]
    dirn = stats["direction"]
    nxt = stats["nxt_ret"]
    scen = ctx["scenarios"]
    today = ctx["frame"].iloc[-1]
    date_str = ctx["asof"].strftime("%Y-%m-%d")
    div = ctx["divergence"].copy()
    div["today"] = div["today"].map(lambda v: _fmt(v))
    div["analogue_median"] = div["analogue_median"].map(lambda v: _fmt(v))
    div["analogue_mad"] = div["analogue_mad"].map(lambda v: _fmt(v))

    stats_rows = ""
    for label, col in [
        ("Next-day return", "nxt_ret"), ("Next-day open gap", "nxt_open_gap"),
        ("Next-day high vs close", "nxt_high_pct"), ("Next-day low vs close", "nxt_low_pct"),
        ("Max adverse excursion (MAD)", "nxt_mad"), ("Max favourable excursion (MAF)", "nxt_maf"),
    ]:
        s = stats.get(col, {})
        if not s.get("count"):
            continue
        stats_rows += (
            f"<tr><td>{label}</td><td>{s['count']}</td><td>{_fmt(s['mean'])}</td>"
            f"<td>{_fmt(s['median'])}</td><td>{_fmt(s['p5'])}</td><td>{_fmt(s['p25'])}</td>"
            f"<td>{_fmt(s['p75'])}</td><td>{_fmt(s['p95'])}</td></tr>"
        )

    bias_color = POS if scen["bias"] == "Bullish" else (NEG if scen["bias"] == "Bearish" else "#8a6d00")
    divergence_html = div.to_html(classes="stats", border=0, index=False)

    context_html = ""
    if ctx.get("context"):
        c = ctx["context"]
        trows = "".join(
            f"<tr><td>{r['series']}</td><td>{r['asof']}</td><td>{r['value']}</td>"
            f"<td>{r['1d %']}</td><td>{r['5d %']}</td><td>{r['1y pctile']}</td></tr>"
            for _, r in c.get("table", pd.DataFrame()).iterrows()
        )
        vix = c.get("vix")
        vix_note = ""
        if vix:
            vix_note = (f"<p><b>India VIX:</b> {vix['level']} ({vix['chg_1d_pct']:+.1f}% d/d) — regime "
                        f"<b>{vix['regime']}</b>, 1y percentile {vix['pctile_1y']:.0f}%.</p>")
        opts = ctx.get("options")
        if opts and opts.get("available"):
            vix_note += (f"<p><b>Options PCR:</b> {opts['last']} ({opts['regime']}) — "
                         f"{opts['n_days']} days of OI data, 120d percentile {opts['pctile_120d']:.0f}% "
                         f"(asof {opts['asof']:%Y-%m-%d}).</p>")
        context_html = f"""
<section>
<h3>4. Market / global context (statistical snapshot)</h3>
{vix_note}
<table class="stats">
<tr><th>Series</th><th>As-of</th><th>Value</th><th>1d %</th><th>5d %</th><th>1y pctile</th></tr>
{trows}
</table>
<p style="color:#555;font-size:12px;">Computed from the cached series. Live items (FII/DII, GIFT Nifty, options OI, macro headlines) are the agent&rsquo;s job in the Interpretation blocks below.</p>
</section>
"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{settings['report']['title']}</title>
<style>
  body {{ font-family: -apple-system, 'Segoe UI', Arial, sans-serif; margin: 28px auto; max-width: 1080px; color: #1a1a1a; background:#fff; }}
  h1 {{ font-size: 22px; margin: 0 0 2px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 18px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin: 14px 0; }}
  .card {{ border:1px solid #ddd; border-radius:8px; padding:10px 14px; min-width:120px; background:#fafafa; }}
  .card .n {{ font-size:20px; font-weight:600; }}
  .card .l {{ font-size:12px; color:#666; }}
  .bias {{ font-size:20px; font-weight:700; padding:10px 16px; border-radius:8px; display:inline-block; color:#fff; background:{bias_color}; }}
  table.stats {{ border-collapse: collapse; width:100%; font-size:13px; }}
  table.stats th, table.stats td {{ border:1px solid #ddd; padding:5px 8px; text-align:right; }}
  table.stats th {{ background:#f2f4f7; }}
  .scen {{ display:flex; gap:12px; flex-wrap:wrap; margin: 12px 0; }}
  .scen > div {{ flex:1; min-width:220px; border:1px solid #ddd; border-radius:8px; padding:10px 14px; }}
  .hsec {{ font-weight:600; color:#8a6d00; font-size:12px; text-transform:uppercase; letter-spacing:.5px; }}
  .isec {{ margin-top:8px; }}
  section {{ margin: 22px 0; }}
  h3 {{ border-bottom: 1px solid #eee; padding-bottom: 4px; }}
  .hist, .interp {{ border-left:3px solid #81a8e0; padding:8px 12px; background:#f7f9fc; }}
  .interp {{ border-left-color:#e0a081; background:#fdf9f6; }}
</style></head><body>
<h1>{settings['report']['title']}</h1>
<div class="meta">Generated {date_str} &middot; NIFTY 50 &middot; analogues: top-{len(ctx['cohort'])} of {stats['analogue_count']} candidates &middot; methodology: historical-analogue engine</div>

<div class="cards">
  <div class="card"><div class="n">{stats['analogue_count']}</div><div class="l">Similar setups found</div></div>
  <div class="card"><div class="n">{dirn['up']}</div><div class="l">Next day positive</div></div>
  <div class="card"><div class="n">{dirn['down']}</div><div class="l">Next day negative</div></div>
  <div class="card"><div class="n">{_fmt(nxt.get('median'))}%</div><div class="l">Median next-day move</div></div>
  <div class="card"><div class="n">{_fmt(nxt.get('p5'))}% &ndash; {_fmt(nxt.get('p95'))}%</div><div class="l">Historical next-day range (P5&ndash;P95)</div></div>
  <div class="card"><div class="n">{_fmt(scen['prob_up'] * 100, 0)}% / {_fmt(scen['prob_down'] * 100, 0)}%</div><div class="l">Up / Down probability</div></div>
</div>
<div style="margin:10px 0;"><span class="bias">{scen['bias']}</span></div>

<section>
<h3>1. Today&rsquo;s technical setup</h3>
<table class="stats">
<tr><th>Close</th><th>RSI(14)</th><th>ATR%</th><th>Gap%</th><th>Range%</th><th>Vol(20d)</th><th>Ret(1d)</th><th>Ret(5d)</th><th>Ret(20d)</th><th>vs SMA20</th><th>vs SMA50</th><th>vs SMA200</th></tr>
<tr>
<td>{_fmt(today['close'], 1)}</td><td>{_fmt(today['rsi_14'])}</td><td>{_fmt(today['atr_pct'])}</td><td>{_fmt(today['gap_pct'])}</td><td>{_fmt(today['range_pct'])}</td>
<td>{_fmt(today['vol_20d'])}</td><td>{_fmt(today['ret_1d'])}</td><td>{_fmt(today['ret_5d'])}</td><td>{_fmt(today['ret_20d'])}</td>
<td>{_fmt(today['dist_sma20'])}</td><td>{_fmt(today['dist_sma50'])}</td><td>{_fmt(today['dist_sma200'])}</td>
</tr></table>
</section>

<section>
<h3>2. Historical analogues &amp; next-day outcomes</h3>
<h4>Next-day distribution &mdash; statistical evidence only</h4>
<table class="stats">
<tr><th>Metric</th><th>n</th><th>Mean</th><th>Median</th><th>P5</th><th>P25</th><th>P75</th><th>P95</th></tr>
{stats_rows}
</table>
<h4>Distribution</h4>
{_img_tag("outcome_hist", images)}
<h4>MAD / MAF &mdash; the excursion you should budget for</h4>
{_img_tag("mad_maf", images)}
</section>

<section>
<h3>3. Current conditions vs historical analogues</h3>
{divergence_html}
<p style="color:#555;font-size:12px;">Raw (not z-scored) feature values: today vs the median and MAD of the analogue cohort. Deviation from zero / analogue-median shows where today&rsquo;s setup is unusual.</p>
</section>

{context_html}

<section>
<h3>5. Scenarios</h3>
<div class="scen">
  <div><h4>🔼 Bullish (stat. prob {_fmt(scen['bullish_scenario']['prob'] * 100, 0)}%)</h4>
    <div class="hist hsec">Historical evidence</div>
    <div>{_fmt(scen['central_case'])}% median next-day move; P75 target +{_fmt(scen['bullish_scenario']['target_median_ret'])}%.</div>
    <div class="interp isec hsec">Interpretation</div>
    <div class="interp">Filled by the Nifty Analyst agent: news, FII/DII, overtight global factors.</div>
  </div>
  <div><h4>➖ Neutral (median band {_fmt(scen['median_band'][0])}% &ndash; {_fmt(scen['median_band'][1])}%)</h4>
    <div class="hist hsec">Historical evidence</div>
    <div>50% of analogous next days land inside the P25&ndash;P75 band.</div>
    <div class="interp isec hsec">Interpretation</div>
    <div class="interp">Filled by the Nifty Analyst agent.</div>
  </div>
  <div><h4>🔻 Bearish (stat. prob {_fmt(scen['bearish_scenario']['prob'] * 100, 0)}%)</h4>
    <div class="hist hsec">Historical evidence</div>
    <div>P25 target {_fmt(scen['bearish_scenario']['target_median_ret'])}%; worst-in-cohort P5 down {_fmt(nxt.get('p5'))}%.</div>
    <div class="interp isec hsec">Interpretation</div>
    <div class="interp">Filled by the Nifty Analyst agent.</div>
  </div>
</div>
<p style="color:#555;font-size:12px;">Probabilities come only from the analogue cohort&rsquo;s next-day distribution. They are not a forecast of guaranteed outcomes.</p>
</section>

<section>
<h3>6. Charts</h3>
{_img_tag("price", images)}
{_img_tag("indicators", images)}
</section>

<p style="color:#888;font-size:11px;">Data: historical EOD from Yahoo Finance via yfinance, point-in-time features, no lookahead. This is research, not investment advice.</p>
</body></html>"""


# ---------------------------------------------------------------- pdf ------
def render_pdf(ctx: dict, settings: dict, path: Path, images: dict) -> None:
    from matplotlib.backends.backend_pdf import PdfPages

    stats = ctx["stats"]
    scen = ctx["scenarios"]
    dirn = stats["direction"]
    nxt = stats["nxt_ret"]

    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis("off")
        lines = [
            f"{settings['report']['title']}",
            f"Generated: {ctx['asof']:%Y-%m-%d}",
            "",
            f"Similar historical setups: {stats['analogue_count']}",
            f"Next day positive: {dirn['up']}   Next day negative: {dirn['down']}",
            f"Median next-day movement: {nxt.get('median') or 0:.2f}%",
            f"Historical next-day range (P5-P95): {nxt.get('p5') or 0:.2f}% to {nxt.get('p95') or 0:.2f}%",
            f"Prob up/down: {scen['prob_up'] * 100:.0f}% / {scen['prob_down'] * 100:.0f}%",
            "",
            f"Statistical bias: {scen['bias']}",
            f"Bullish target (P75): {scen['bullish_scenario']['target_median_ret']:.2f}%",
            f"Bearish target (P25): {scen['bearish_scenario']['target_median_ret']:.2f}%",
            "",
            "NOTE: probabilities are derived solely from the analogue cohort.",
            "Interpretation sections are added by the Nifty Analyst agent.",
        ]
        ax.text(0.04, 0.98, "\n".join(lines), va="top", fontsize=11, family="monospace")
        pdf.savefig(fig)
        plt.close(fig)

        for png in images.values():
            from matplotlib.image import imread

            fig = plt.figure(figsize=(8.27, 4.2))
            fig.figimage(imread(png, format="png"), 0, 0, origin="upper", cmap="gray")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)


# ---------------------------------------------------------------- intraday --
def intraday_session_chart(frame, settings) -> BytesIO:
    target = frame.index.max().normalize()
    day = frame[frame.index.date == target.date()]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(day.index, day["close"], color="#222", lw=1.2, label="Close")
    ax.fill_between(day.index, day["low"], day["high"], color="#aec8f5", alpha=0.35, label="Range")
    ax.scatter([frame.index[-1]], [frame["close"].iloc[-1]], marker="*", s=160, color=NEG, zorder=5, label="Target bar")
    ax.set_title(f"Target session {target.date()} ({int(round((frame.index[1]-frame.index[0]).total_seconds()/60))}m)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylabel("Index level")
    fig.tight_layout()
    return _fig_to_png(fig)


def intraday_histogram(stats, primary="rest_of_session") -> BytesIO:
    s = stats[primary]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(stats["raw"], bins=40, color="#aec8f5", edgecolor="#5b8dd9")
    ax.axvline(0, color="#333", lw=1)
    for p, c, ls in [("p5", "#888", "--"), ("p25", NEG, ":"), ("median", "#222", "-"), ("p75", POS, ":"), ("p95", "#888", "--")]:
        if p in s:
            ax.axvline(s[p], color=c, ls=ls, lw=1)
    ax.set_title(f"{primary} of {s['count']} analogous bars (ret %)")
    ax.set_xlabel("Rest-of-session return (%)")
    ax.set_ylabel("Frequency")
    fig.tight_layout()
    return _fig_to_png(fig)


def write_intraday_report(ctx: dict, settings: dict, include_pdf: bool = True) -> tuple:
    folder = settings_mod.rel(settings, "reports_dir") / settings["paths"]["intraday_reports_subdir"]
    folder.mkdir(parents=True, exist_ok=True)
    tf = ctx["tf"]
    k = ctx["k"]
    est = ctx["stats"][ctx["target"]]
    dirn = ctx["stats"]["direction"]

    rows = ""
    for col in [ctx["target"], "fwd_ret_1"] + [f"fwd_ret_{h}" for h in ctx["settings"]["intraday"]["horizon_bars"]]:
        s = ctx["stats"].get(col)
        if not s or not s.get("count"):
            continue
        rows += (f"<tr><td>{col}</td><td>{s['count']}</td><td>{_fmt(s['mean'])}</td>"
                 f"<td>{_fmt(s['median'])}</td><td>{_fmt(s['p5'])}</td><td>{_fmt(s['p25'])}</td>"
                 f"<td>{_fmt(s['p75'])}</td><td>{_fmt(s['p95'])}</td></tr>")

    anal_rows = ""
    for ts, r in ctx["analogues"].tail(20).iterrows():
        anal_rows += (f"<tr><td>{ts:%Y-%m-%d %H:%M}</td>"
                      f"<td>{_fmt(r['fwd_ret_1'])}</td><td>{_fmt(r['rest_of_session'])}</td></tr>")

    img = {k_: base64.b64encode(v.getvalue()).decode() for k_, v in ctx["images"].items()}
    direction_note = ""
    if ctx["backtest"]:
        bt = ctx["backtest"]
        direction_note = (f"<p><b>Walk-forward gate ({bt['n_days']} bars):</b> hit-rate {bt['hit_rate']*100:.1f}% vs "
                          f"always-rest-up {bt['always_up_acc']*100:.1f}% &rarr; edge {bt['edge']:+.2f}pp, "
                          f"corr {bt['corr']:.3f}, MAE {bt['mae']:.2f}% (took {bt['seconds']}s)</p>")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Intraday analogue report</title><style>
  body{{font-family:'Segoe UI',Arial,sans-serif;margin:28px auto;max-width:1080px;color:#1a1a1a;}}
  .meta{{color:#666;font-size:13px;margin-bottom:18px;}}
  .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0;}}
  .card{{border:1px solid #ddd;border-radius:8px;padding:10px 14px;min-width:120px;background:#fafafa;}}
  .card .n{{font-size:20px;font-weight:600;}} .card .l{{font-size:12px;color:#666;}}
  table{{border-collapse:collapse;width:100%;font-size:13px;}} td,th{{border:1px solid #ddd;padding:5px 8px;}}
  th{{background:#f2f4f7;}} section{{margin:22px 0;}} h3{{border-bottom:1px solid #eee;padding-bottom:4px;}}
</style></head><body>
<h1>Intraday analogue report &mdash; {tf}m NIFTY 50</h1>
<div class="meta">As-of {ctx['asof']:%Y-%m-%d %H:%M} &middot; target bar {ctx['target_ts']:%Y-%m-%d %H:%M} &middot; K={k} &middot; features: {len(ctx['features'])} &middot; methodology: historical-analogue engine</div>

<div class="cards">
  <div class="card"><div class="n">{est['count']}</div><div class="l">Similar bars</div></div>
  <div class="card"><div class="n">{dirn['up']} / {dirn['down']}</div><div class="l">Up / down rest-of-session</div></div>
  <div class="card"><div class="n">{_fmt(ctx['stats'].get('fwd_ret_1', {}).get('median'))}%</div><div class="l">Median next-bar move</div></div>
  <div class="card"><div class="n">{_fmt(est.get('median'))}%</div><div class="l">Median rest-of-session</div></div>
  <div class="card"><div class="n">{_fmt(est.get('p5'))}% &ndash; {_fmt(est.get('p95'))}%</div><div class="l">Rest-of-session P5&ndash;P95</div></div>
</div>

<section>
<h3>1. Target session</h3>
<img src="data:image/png;base64,{img['session']}" style="max-width:100%;height:auto">
{direction_note}
</section>

<section>
<h3>2. Cohort forward-outcome distribution (statistical evidence only)</h3>
<table>
<tr><th>Metric</th><th>n</th><th>Mean</th><th>Median</th><th>P5</th><th>P25</th><th>P75</th><th>P95</th></tr>
{rows}
</table>
<img src="data:image/png;base64,{img['hist']}" style="max-width:100%;height:auto">
</section>

<section>
<h3>3. Closest analogous bars (last 20 shown)</h3>
<table>
<tr><th>Bar</th><th>Next-bar ret %</th><th>Rest-of-session %</th></tr>
{anal_rows}
</table>
</section>

<p style="color:#888;font-size:11px;">Data: 5m free yfinance collector (recent) + optional Zerodha Kite backfill (2015+). Point-in-time features, no lookahead. Research, not advice.</p>
</body></html>"""

    html_path = folder / f"intraday-{tf}m-{ctx['asof']:%Y-%m-%d}.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path, None


def make_charts(ctx: dict) -> dict:
    frame = ctx["frame"]
    ma_periods = [n for n in ctx["settings"]["indicators"]["ma_periods"] if f"sma_{n}" in frame]
    return {
        "price": price_chart(frame, ctx["analogue_positions"], ma_periods),
        "indicators": indicator_chart(frame),
        "outcome_hist": outcome_histogram(ctx),
        "mad_maf": mad_maf_chart(ctx),
    }


def write_full_report(ctx: dict, settings: dict) -> tuple:
    folder = settings_mod.rel(settings, "reports_dir") / settings["paths"]["daily_reports_subdir"]
    folder.mkdir(parents=True, exist_ok=True)
    images = make_charts(ctx)
    html = render_html(ctx, settings, images)
    html_path = folder / f"daily-{ctx['asof']:%Y-%m-%d}.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = folder / f"daily-{ctx['asof']:%Y-%m-%d}.pdf"
    render_pdf(ctx, settings, pdf_path, images)
    return html_path, pdf_path


def write_backtest_report(res: dict, ctx: dict, settings: dict) -> tuple:
    folder = settings_mod.rel(settings, "reports_dir") / settings["paths"]["backtest_reports_subdir"]
    folder.mkdir(parents=True, exist_ok=True)
    date_str = ctx["asof"].strftime("%Y-%m-%d")
    if not res.get("ok"):
        summary = "<p>No backtest rows produced (insufficient history).</p>"
        html = f"<html><body><h1>Backtest validation</h1>{summary}</body></html>"
        html_path = folder / f"validation-{date_str}.html"
        html_path.write_text(html, encoding="utf-8")
        return html_path, None

    f = lambda v, nd=3: (f"{v:.{nd}f}") if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)) else "-"
    cards = f"""
    <div class="cards">
      <div class="card"><div class="n">{res['n_days']}</div><div class="l">Test days</div></div>
      <div class="card"><div class="n">{f(res['hit_rate'] * 100, 1)}%</div><div class="l">Direction hit-rate</div></div>
      <div class="card"><div class="n">{f(res['always_up_acc'] * 100, 1)}%</div><div class="l">Always-up baseline</div></div>
      <div class="card"><div class="n">{f(res['edge'] * 100, 1)}%</div><div class="l">Edge (hit - baseline)</div></div>
      <div class="card"><div class="n">{f(res['corr'])}</div><div class="l">Pred vs actual corr</div></div>
      <div class="card"><div class="n">{f(res['mae'])}</div><div class="l">MAE (median pred)</div></div>
      <div class="card"><div class="n">{f(res['baseline_mean'])}%</div><div class="l">Baseline mean next-day</div></div>
      <div class="card"><div class="n">{f(res['n_strong'])}</div><div class="l">Strong-bullish days</div></div>
      <div class="card"><div class="n">{f(res['n_weak'])}</div><div class="l">Weak/bearish days</div></div>
      <div class="card"><div class="n">{f(res['strong_mean_actual'])}%</div><div class="l">Actual mean on strong days</div></div>
      <div class="card"><div class="n">{f(res['weak_mean_actual'])}%</div><div class="l">Actual mean on weak days</div></div>
    </div>"""

    rec = res["records"].copy()
    rec["date"] = rec["date"].dt.strftime("%Y-%m-%d")
    rec = rec.round(3)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Backtest validation</title>
<style> body{{font-family:'Segoe UI',Arial,sans-serif;margin:28px auto;max-width:1080px;}} .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0;}}
.card{{border:1px solid #ddd;border-radius:8px;padding:10px 14px;min-width:120px;background:#fafafa;}} .card .n{{font-size:18px;font-weight:600;}} .card .l{{font-size:12px;color:#666;}}
table{{border-collapse:collapse;width:100%;font-size:12px;}} td,th{{border:1px solid #ddd;padding:4px 8px;}} th{{background:#f2f4f7;}}</style></head><body>
<h1>Backtest validation &mdash; walk-forward analogue methodology</h1>
<p>Run: {date_str} &middot; window: {settings['backtest']['window_years']}y &middot; K={settings['analogues']['k']} &middot; lookback {settings['analogues']['standardize_lookback']}d &middot; took {res['seconds']}s</p>
{cards}
<p style="color:#555;font-size:12px;">Hit-rate &gt; always-up baseline and t_mean material are signs of genuine edge. Weak numbers mean the feature set needs tuning before Phase-2 live inputs are added.</p>
<h3>Daily records</h3>
{rec.to_html(border=0, index=False)}
</body></html>"""
    html_path = folder / f"validation-{date_str}.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path, None