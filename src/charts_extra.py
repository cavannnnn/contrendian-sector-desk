"""Charts for the qualitative overlay: second-order transmission map, secular vs cyclical
matrix, alternative-data signals, cross-region comparison."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

import config as C
from report import BLUE, RED, GRAY, INK, INK2, GRID, SURFACE, _heat, _save


def chart_second_order():
    shocks = [("Iran war / Hormuz\nWTI $93-96", 0.82), ("Fed hikes + 10Y 5.3%\nbond selloff", 0.50),
              ("AI capex boom\n$600bn+ hyperscalers", 0.18)]
    first = [("Energy XLE", 0.92, +1), ("Airlines/transports XLI", 0.76, -1), ("Utilities XLU", 0.60, -1),
             ("Real Estate XLRE", 0.47, -1), ("Banks XLF (NIM)", 0.34, +1), ("Semis / IT XLK", 0.18, +1),
             ("Power demand XLU", 0.04, +1)]
    second = [("Consumer wallet: gas $4.35\n→ Discretionary XLY", 0.88, -1),
              ("Diesel / feedstock costs\n→ Chemicals XLB", 0.70, -1),
              ("Mortgage 7.4% → housing freeze\n→ XLY, XLB, XLRE", 0.50, -1),
              ("Deposit costs, card delinquencies\n→ XLF", 0.32, -1),
              ("Grid, copper, gas turbines\n→ XLI, XLB, XLE", 0.14, +1)]
    links1 = [(0, 0, +1), (0, 1, -1), (1, 2, -1), (1, 3, -1), (1, 4, +1), (2, 5, +1), (2, 6, +1)]
    links2 = [(0, 0, -1), (0, 1, -1), (1, 2, -1), (4, 3, -1), (6, 4, +1), (5, 4, +1)]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.set_xlim(-0.01, 1); ax.set_ylim(-0.05, 1.02); ax.axis("off")
    X = [0.09, 0.42, 0.79]
    def box(x, y, txt, edge, w=0.17, h=0.09):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.008,rounding_size=0.01",
                                    fc=SURFACE, ec=edge, lw=1.4))
        ax.text(x, y, txt, ha="center", va="center", fontsize=7.6, color=INK)
    for t, y in shocks:
        box(X[0], y, t, INK2, w=0.17, h=0.12)
    for t, y, s in first:
        box(X[1], y, ("▲ " if s > 0 else "▼ ") + t, BLUE if s > 0 else RED, w=0.2, h=0.07)
    for t, y, s in second:
        box(X[2], y, ("▲ " if s > 0 else "▼ ") + t, BLUE if s > 0 else RED, w=0.27, h=0.1)
    def arrow(x0, y0, x1, y1, s):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=9, lw=1,
                                     color=BLUE if s > 0 else RED, alpha=0.75, connectionstyle="arc3,rad=0.0"))
    for a, b, s in links1:
        arrow(X[0] + 0.088, shocks[a][1], X[1] - 0.103, first[b][1], s)
    for a, b, s in links2:
        arrow(X[1] + 0.103, first[a][1], X[2] - 0.138, second[b][1], s)
    for x, t in zip(X, ["Shock (Oct 2026)", "1st-order effect", "2nd / 3rd-order effect"]):
        ax.text(x, 1.0, t, ha="center", fontsize=9.5, fontweight="bold", color=INK)
    ax.text(0, -0.04, "▲ / blue = positive for the sector, ▼ / red = negative", fontsize=7.5, color=INK2)
    _save(fig, "08_second_order_map")


def chart_secular_cyclical(tab):
    sec = pd.Series({k: v[0] for k, v in C.SECULAR.items()})
    cyc = tab["Composite"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.axhline(0, color=GRAY, lw=0.8); ax.axvline(0, color=GRAY, lw=0.8)
    for t in C.SECTORS:
        call = tab.at[t, "Call"]
        c = BLUE if call == "LONG" else RED if call == "SHORT" else GRAY
        ax.scatter(cyc[t], sec[t], s=70, color=c, edgecolor=SURFACE, lw=2, zorder=3)
        off = {"XLI": (6, -13), "XLU": (-8, 6)}.get(t, (6, 4))
        ax.annotate(f"{t}{' (' + call + ')' if call else ''}", (cyc[t], sec[t]), xytext=off,
                    ha="right" if t == "XLU" else "left",
                    textcoords="offset points", fontsize=8, color=INK)
    lim = 2.6
    ax.set_xlim(-lim, lim); ax.set_ylim(-1.6, 2.75)
    kw = dict(fontsize=8, color=INK2, style="italic")
    ax.text(lim - 0.05, 2.7, "Best longs:\nsecular + cyclical tailwind", ha="right", va="top", **kw)
    ax.text(-lim + 0.05, -1.5, "Best shorts:\nsecular + cyclical headwind", ha="left", va="bottom", **kw)
    ax.text(-lim + 0.05, 2.7, "Buy-the-dip watchlist", ha="left", va="top", **kw)
    ax.text(lim - 0.05, -1.5, "Tactical only (trade, don't own)", ha="right", va="bottom", **kw)
    ax.set_xlabel("Cyclical score (model composite, 1-7y horizon)")
    ax.set_ylabel("Secular score (10-40y structural, judgemental)")
    ax.set_title("Secular vs cyclical positioning")
    _save(fig, "09_secular_vs_cyclical")


def chart_alt(alt):
    d = alt.dropna(subset=["Signal"]).sort_values("Signal")
    fig, ax = plt.subplots(figsize=(7.6, 6))
    y = np.arange(len(d))
    ax.barh(y, d["Signal"], color=[BLUE if v > 0 else RED for v in d["Signal"]], height=0.62)
    sect = [", ".join(f"{'+' if w > 0 else '−'}{s}" for s, w in m.items()) for m in d["Sectors"]]
    ax.set_yticks(y, [f"{i}  [{s}]" for i, s in zip(d["Indicator"], sect)], fontsize=7.5)
    ax.axvline(0, color=GRAY, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Signed signal (z vs 5y; + = supportive for '+' sectors)")
    ax.set_title("Alternative-data overlay: latest reading vs own 5-year history")
    _save(fig, "10_alt_data_signals")


def chart_regions(comp):
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    _heat(ax, comp, "+.2f", vmax=2.5)
    ax.set_title("Composite by region (same framework)")
    ax.xaxis.tick_top()
    _save(fig, "11_region_comparison")
