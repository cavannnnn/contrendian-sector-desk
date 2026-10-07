"""Charts (PNG, for the proposal), Excel workbook and a markdown weekly brief."""
from __future__ import annotations

from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import matplotlib.dates
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

import config as C
import model as M

# Reference palette (dataviz skill), light mode
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, RED, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#e34948", "#8a8984"
DIVERGE = LinearSegmentedColormap.from_list("div", ["#c8312f", "#e34948", "#f3b3ad", "#f0efec",
                                                    "#9ec5f4", "#2a78d6", "#1c5cab"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "lines.linewidth": 2, "legend.frameon": False,
})


def _save(fig, name):
    C.CHARTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(C.CHARTS / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _heat(ax, df, fmt, vmax=None, pct=False):
    vals = df.values.astype(float)
    vmax = vmax or np.nanmax(np.abs(vals))
    ax.imshow(vals, cmap=DIVERGE, vmin=-vmax, vmax=vmax, aspect="auto")
    ax.grid(False)
    ax.set_xticks(range(df.shape[1]), df.columns, rotation=0)
    ax.set_yticks(range(df.shape[0]), df.index)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            v = vals[i, j]
            if np.isnan(v):
                continue
            txt = f"{v:+.1%}" if pct else format(v, fmt)
            ax.text(j, i, txt, ha="center", va="center", fontsize=8,
                    color="white" if abs(v) > 0.6 * vmax else INK)
    ax.set_xticks(np.arange(-.5, df.shape[1]), minor=True)
    ax.set_yticks(np.arange(-.5, df.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)


def chart_scores(tab):
    df = tab[["Macro", "Fundamental", "Technical", "Composite"]].copy()
    df.index = [f"{tab.at[i, 'Call'] + '  ' if tab.at[i, 'Call'] else ''}{C.SECTORS[i]} ({i})" for i in tab.index]
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    _heat(ax, df, "+.2f", vmax=2.5)
    ax.set_title(f"Sector scores (z), as of {tab.attrs['asof']:%d %b %Y}  ·  weights 40 / 30 / 30")
    ax.xaxis.tick_top()
    _save(fig, "01_sector_scores")


def chart_regime_heatmap(sig):
    df = M.regime_heatmap_table(sig)
    fig, ax = plt.subplots(figsize=(7, 4.6))
    _heat(ax, df, "", vmax=0.15, pct=True)
    ax.set_title("Avg. annualised excess return vs. equal-weight sectors, by macro regime (2000-2026)")
    ax.xaxis.tick_top()
    _save(fig, "02_regime_sector_heatmap")


def chart_backtest(res):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 5.2), height_ratios=[2.2, 1], sharex=True)
    series = [("long_only", "Long top-3", BLUE), ("eq_sectors", "Equal-weight sectors", GRAY),
              ("long_short", "Long/short (3 vs 3)", ORANGE)]
    for col, lab, c in series:
        eq = (1 + res[col]).cumprod() * 100
        a1.plot(eq.index, eq, color=c, label=lab, lw=1.8 if col != "eq_sectors" else 1.4)
        a1.annotate(f"{lab} {eq.iloc[-1]:.0f}", (eq.index[-1], eq.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=8, color=INK2)
        dd = eq / eq.cummax() - 1
        if col != "eq_sectors":
            a2.plot(dd.index, dd * 100, color=c, lw=1.2)
    a1.set_yscale("log")
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}"))
    a1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    a1.set_yticks([60, 100, 200, 400, 800])
    a1.set_title("Backtest 2005-2026, monthly signals, 3-month overlapping holds, 10bp costs (growth of 100, log)")
    a1.legend(loc="upper left")
    a2.set_title("Drawdown (%)")
    a2.axhline(0, color=GRID, lw=1)
    for x0, x1 in [("2007-10", "2009-03"), ("2020-02", "2020-04"), ("2022-01", "2022-10")]:
        for a in (a1, a2):
            a.axvspan(pd.Timestamp(x0), pd.Timestamp(x1), color="#f0efec", zorder=0, lw=0)
    fig.tight_layout()
    _save(fig, "03_backtest")


def chart_macro(sig):
    r = sig["regimes"].loc["2019":]
    panels = [("dgs10", "10Y Treasury yield (%)"), ("cpi_yoy", "CPI YoY (%)"), ("ppi_yoy", "PPI YoY (%)"),
              ("wti", "WTI crude ($/bbl)"), ("unrate", "Unemployment rate (%)"), ("sentiment", "UMich consumer sentiment"),
              ("curve", "10Y-2Y curve (pp)"), ("baa_spread", "Baa - 10Y credit spread (pp)"), ("cu_au", "Copper / gold ratio (x1000)")]
    fig, axes = plt.subplots(3, 3, figsize=(9, 6.2), sharex=True)
    for ax, (col, title) in zip(axes.flat, panels):
        s = r[col].dropna() * (1000 if col == "cu_au" else 1)
        ax.plot(s.index, s, color=BLUE, lw=1.5)
        ax.scatter([s.index[-1]], [s.iloc[-1]], color=BLUE, s=18, zorder=3)
        ax.annotate(f"{s.iloc[-1]:.2f}",
                    (s.index[-1], s.iloc[-1]), xytext=(-4, 7), textcoords="offset points",
                    ha="right", fontsize=8, color=INK)
        ax.set_title(title, fontsize=9)
        ax.tick_params(labelsize=7.5)
    fig.suptitle("Macro dashboard (point-in-time, month-end)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    _save(fig, "04_macro_dashboard")


def chart_relative_strength(sig, tab):
    rs = sig["tech_daily"]["rel_strength"]
    rs = rs[rs.index >= rs.index[-1] - pd.DateOffset(years=1)]
    picks = list(tab.index[tab.Call == "LONG"]) + list(tab.index[tab.Call == "SHORT"])
    fig, axes = plt.subplots(2, 3, figsize=(9, 4.6), sharey=True)
    for ax, t in zip(axes.flat, picks):
        s = rs[t] / rs[t].iloc[0] * 100
        c = BLUE if tab.at[t, "Call"] == "LONG" else RED
        ax.plot(s.index, s, color=c, lw=1.5)
        ax.axhline(100, color=GRAY, lw=0.8)
        ax.set_title(f"{tab.at[t, 'Call']}  {C.SECTORS[t]} ({t})  {s.iloc[-1] - 100:+.1f}%", fontsize=9)
        ax.tick_params(labelsize=7.5)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    fig.suptitle("Relative strength vs. SPY, last 12 months (indexed to 100)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    _save(fig, "05_relative_strength_picks")


def chart_scenarios(scen):
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _heat(ax, scen, "", vmax=0.15, pct=True)
    ax.set_title("Scenario analysis: historical annualised excess return in each scenario's regime")
    ax.xaxis.tick_top()
    ax.set_xticks(range(scen.shape[1]), [c.replace(" (", "\n(") for c in scen.columns], fontsize=8)
    _save(fig, "06_scenarios")


def chart_regime_timeline(sig):
    r = sig["regimes"].loc["2005":]
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.plot(r.index, r.growth_score, color=BLUE, lw=1.4, label="Growth momentum")
    ax.plot(r.index, r.inflation_score, color=ORANGE, lw=1.4, label="Inflation momentum")
    ax.axhline(0, color=GRAY, lw=0.8)
    ax.legend(loc="lower left", ncols=2)
    last = r.iloc[-1]
    ax.set_title(f"Regime inputs (expanding z-scores)  ·  now: {last.quadrant}, rates {last.rates}")
    _save(fig, "07_regime_timeline")


def write_excel(sig, tab, fund, bt, stats, attrib, sub, ic, scen, regheat, extra=None):
    path = C.OUT / f"sector_scores_{date.today()}.xlsx"
    reg = sig["regimes"].copy()
    hist = bt["returns"]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        tab.to_excel(xw, sheet_name="Live scores")
        fund.to_excel(xw, sheet_name="Fundamentals")
        reg.iloc[-60:].iloc[::-1].to_excel(xw, sheet_name="Macro regimes")
        regheat.to_excel(xw, sheet_name="Regime x sector")
        scen.to_excel(xw, sheet_name="Scenarios")
        stats.to_excel(xw, sheet_name="Backtest stats")
        attrib.to_excel(xw, sheet_name="Layer attribution")
        sub.to_excel(xw, sheet_name="Sub-periods")
        ic.to_excel(xw, sheet_name="Signal IC")
        hist.iloc[::-1].to_excel(xw, sheet_name="Monthly picks history")
        bt["score"].iloc[::-1].to_excel(xw, sheet_name="Composite score history")
        for name, df in (extra or {}).items():
            df.to_excel(xw, sheet_name=name)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "B2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    10, min(34, max(len(str(c.value or "")) for c in col[:50]) + 2))
    return path


def write_brief(sig, tab, stats, news: str | None = None, regions=None):
    r = sig["regimes"].iloc[-1]
    longs, shorts = tab.index[tab.Call == "LONG"], tab.index[tab.Call == "SHORT"]
    fmt = lambda idx: ", ".join(f"{C.SECTORS[t]} ({t}, {tab.at[t, 'Composite']:+.2f})" for t in idx)
    lines = [
        f"# Sector rotation weekly brief, {date.today()}",
        "",
        f"**Regime:** {r.quadrant} (growth {r.growth_score:+.2f}, inflation {r.inflation_score:+.2f}), "
        f"10Y rates {r.rates} ({r.dgs10:.2f}%), credit spreads {r.credit}.",
        "",
        f"**LONG:** {fmt(longs)}  ",
        f"**SHORT:** {fmt(shorts)}",
        "",
        "| Ticker | Sector | Macro | Fund. | Tech. | Composite | RSI | Call |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t, x in tab.iterrows():
        lines.append(f"| {t} | {x.Sector} | {x.Macro:+.2f} | {x.Fundamental:+.2f} | {x.Technical:+.2f} | "
                     f"{x.Composite:+.2f} | {x['RSI(14)']:.0f} | {x.Call} |")
    ls = stats.loc["L/S (3 long - 3 short)"]
    lines += ["", f"Backtest (2005-now, L/S): ann. {ls['Ann. return']:+.1%}, Sharpe {ls['Sharpe (rf=0)']:.2f}, "
              f"max DD {ls['Max drawdown']:.0%}.", ""]
    if regions is not None:
        lines += ["## Cross-region composite", "", regions.round(2).to_markdown(), ""]
    ov = tab[[c for c in ["Alt-data overlay", "News sentiment", "Secular"] if c in tab]].round(2)
    lines += ["## Qualitative overlay inputs", "", ov.to_markdown(), ""]
    if news:
        lines += ["## News & policy scan (LLM agent)", "", news, ""]
    path = C.OUT / f"weekly_brief_{date.today()}.md"
    path.write_text("\n".join(lines))
    return path


def latest_news_scan() -> tuple[str | None, dict | None]:
    """Markdown + raw dict for the most recent saved news scan (agent or in-session)."""
    import json
    files = sorted((C.DATA / "news").glob("*.json"))
    if not files:
        return None, None
    d = json.loads(files[-1].read_text())
    sc = d.get("scan", d)
    lines = [f"*Scan date: {files[-1].stem}*", "",
             f"**Policy stance:** {sc['policy_stance']}: {sc['policy_summary']}", "", "**Shocks / events**"]
    lines += [f"- *{x['event']}* ({x['category']}). 1st order: {x['first_order']}. 2nd order: {x['second_order']}"
              for x in sc["shocks"]]
    lines += ["", "**Sector read-through**"] + [f"- {v['ticker']}: {v['sentiment']}, {v['reason']}" for v in sc["sector_views"]]
    lines += ["", "**Conflicts with model calls**"] + [f"- {f}" for f in sc["flags_vs_model"]]
    if d.get("sources"):
        lines += ["", "Sources: " + " · ".join(d["sources"])]
    return "\n".join(lines), sc


def build_all(sig, news: str | None = None):
    import alt_data as A
    import charts_extra as X
    import international as I
    tab, fund = M.live_scores(sig)
    if news is None:
        news, scan = latest_news_scan()
    else:
        scan = None
    alt = A.alt_signals()
    tab["Alt-data overlay"] = A.alt_sector_overlay(alt)
    if scan:
        sent = {v["ticker"]: {"positive": 1, "neutral": 0, "negative": -1}[v["sentiment"]] for v in scan["sector_views"]}
        tab["News sentiment"] = pd.Series(sent)
    tab["Secular"] = pd.Series({k: v[0] for k, v in C.SECULAR.items()})
    regions = I.comparison(tab, sig["macro"].iloc[-1])
    bt = M.backtest(sig)
    stats = M.stats_table(bt["returns"])
    attrib = M.layer_attribution(sig)
    sub = M.subperiod_stats(bt["returns"])
    ic = M.signal_ic(sig)
    scen = M.scenario_table(sig)
    regheat = M.regime_heatmap_table(sig)
    chart_scores(tab)
    chart_regime_heatmap(sig)
    chart_backtest(bt["returns"])
    chart_macro(sig)
    chart_relative_strength(sig, tab)
    chart_scenarios(scen)
    chart_regime_timeline(sig)
    X.chart_second_order()
    X.chart_secular_cyclical(tab)
    X.chart_alt(alt)
    X.chart_regions(regions)
    extra = {"Alt data": alt.assign(Sectors=alt.Sectors.astype(str)), "Regions": regions,
             "Secular rationale": pd.DataFrame(C.SECULAR, index=["score", "rationale"]).T}
    if scan:
        extra["News shocks"] = pd.DataFrame(scan["shocks"])
        extra["News sector views"] = pd.DataFrame(scan["sector_views"])
    xl = write_excel(sig, tab, fund, bt, stats, attrib, sub, ic, scen, regheat, extra)
    md = write_brief(sig, tab, stats, news, regions)
    return {"table": tab, "excel": xl, "brief": md, "stats": stats}
