"""Framework flow diagram for page 1 of the proposal."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from report import BLUE, ORANGE, AQUA, GRAY, INK, INK2, SURFACE, _save


def chart_framework():
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    def box(x, y, w, h, title, body, edge):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012", fc=SURFACE, ec=edge, lw=1.6))
        ax.text(x + w / 2, y + h - 0.045, title, ha="center", va="top", fontsize=8, fontweight="bold", color=INK)
        ax.text(x + w / 2, y + (h - 0.09) / 2, body, ha="center", va="center", fontsize=6.5, color=INK2, linespacing=1.3)
    def arr(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=10, lw=1.1, color=GRAY))
    box(0.005, 0.06, 0.165, 0.88, "Agentic pipeline",
        "weekly cron\n(GitHub Actions)\n\nyfinance · FRED · SSGA\nTSA · Google Trends\nFed / EIA RSS\n\nClaude news agent\n(structured shocks)\n\n→ DuckDB / parquet\ndated snapshots", GRAY)
    lay = [(0.66, "Macro 40%", "growth × inflation quadrant\n+ rate direction (a-priori maps)", BLUE),
           (0.36, "Fundamental 30%", "value · quality · growth\n(top-25 holdings)\n+ div. yield vs own 10y history", ORANGE),
           (0.06, "Technical 30%", "12-1m rel. momentum · 200d trend\nMACD · VWAP\nRSI(14) filter", AQUA)]
    for y, t, b, c in lay:
        box(0.21, y, 0.235, 0.28, t, b, c)
        arr(0.17, 0.5, 0.21, y + 0.14)
        arr(0.445, y + 0.14, 0.485, 0.5)
    box(0.485, 0.27, 0.155, 0.46, "Composite z", "rank 11 sectors\n\ntop-3 long\nbottom-3 short\n\n3 overlapping\nmonthly tranches", INK)
    box(0.675, 0.27, 0.155, 0.46, "Overlay", "secular vs cyclical\n2nd-order effects\nalt data · news\nscenarios\n\n(max one notch,\nreason in writing)", INK2)
    box(0.865, 0.27, 0.13, 0.46, "Book", "3 long / 3 short\n\nconviction-sized\n\nstops &\nre-test triggers", INK)
    arr(0.64, 0.5, 0.675, 0.5); arr(0.83, 0.5, 0.865, 0.5)
    _save(fig, "00_framework")
