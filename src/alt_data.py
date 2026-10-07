"""Alternative / unconventional indicators and their sector read-through.

Not part of the backtested composite (no clean point-in-time history for most), but
shown next to it as an overlay used in the qualitative adjustment step.
"""
from __future__ import annotations

import io
import time

import numpy as np
import pandas as pd
import requests

import config as C
from collect import _store, UA

# id -> (label, transform, sign, {sector: +1/-1}, rationale)
# transform: "yoy" % change over 12 months, "chg3" 3-month change in level, "lvl_z" level z-score
ALT_FRED = {
    "IHLIDXUS": ("Indeed job postings", "yoy", +1, {"XLY": 1, "XLI": 1, "XLF": 1}, "labour demand leads payrolls"),
    "HOUST": ("Housing starts", "yoy", +1, {"XLB": 1, "XLY": 1, "XLI": 1}, "lumber, cement, appliances, home improvement"),
    "PERMIT": ("Building permits", "yoy", +1, {"XLB": 1, "XLY": 1}, "leads starts by 1-2 months"),
    "MORTGAGE30US": ("30Y mortgage rate", "chg3", -1, {"XLRE": 1, "XLY": 1, "XLF": 1}, "housing turnover, refi income"),
    "TRUCKD11": ("Truck tonnage", "yoy", +1, {"XLI": 1, "XLB": 1}, "physical goods volumes"),
    "IPG2211S": ("Electric power generation", "yoy", +1, {"XLU": 1, "XLI": 1}, "AI/data-centre load growth"),
    "NEWORDER": ("Core capital goods orders", "yoy", +1, {"XLI": 1, "XLK": 1}, "business capex intentions"),
    "RSAFS": ("Retail sales (nominal)", "yoy", +1, {"XLY": 1, "XLP": 1}, "consumer demand"),
    "TOTALSA": ("Light vehicle sales", "yoy", +1, {"XLY": 1}, "big-ticket discretionary"),
    "GASREGW": ("Retail gasoline price", "yoy", -1, {"XLY": 1, "XLE": -1}, "tax on consumer wallets; refiner margins"),
    "DTWEXBGS": ("Trade-weighted USD", "yoy", -1, {"XLK": 1, "XLB": 1, "XLI": 1}, "foreign-sales translation for exporters"),
    "VIXCLS": ("VIX", "lvl_z", -1, {"XLY": 1, "XLK": 1, "XLF": 1}, "risk appetite"),
    "DRCCLACBS": ("Credit-card delinquency rate", "chg3", -1, {"XLF": 1, "XLY": 1}, "consumer credit stress"),
    "TOTBKCR": ("Bank credit", "yoy", +1, {"XLF": 1}, "loan growth drives NII"),
    "PCU325211325211": ("Plastics resin PPI", "yoy", +1, {"XLB": 1}, "chemical pricing power"),
}
TRENDS = {  # Google search term -> (sign, {sector: +1/-1}, rationale)
    "recession": (-1, {"XLY": 1, "XLF": 1, "XLI": 1, "XLP": -1, "XLV": -1}, "household fear gauge"),
    "layoffs": (-1, {"XLY": 1, "XLF": 1}, "labour stress before claims"),
    "gas prices": (-1, {"XLY": 1, "XLE": -1}, "salience of fuel costs"),
    "Ozempic": (+1, {"XLV": 1, "XLP": -1}, "GLP-1 adoption: pharma up, snacks down"),
    "data center": (+1, {"XLU": 1, "XLI": 1, "XLK": 1}, "AI build-out attention"),
}


def collect_alt() -> None:
    out = {}
    for sid in ALT_FRED:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers=UA, timeout=30)
        s = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=".").iloc[:, 0]
        out[sid] = s.astype(float)
    _store(pd.DataFrame(out).sort_index(), "alt_fred")

    tsa = []
    for path in ["", "/2025", "/2024"]:
        r = requests.get(f"https://www.tsa.gov/travel/passenger-volumes{path}", headers=UA, timeout=30)
        t = pd.read_html(io.StringIO(r.text))[0]
        t["Date"] = pd.to_datetime(t["Date"])
        tsa.append(t.set_index("Date")["Numbers"])
    _store(pd.concat(tsa).sort_index().groupby(level=0).last().to_frame("tsa"), "alt_tsa")

    try:
        from pytrends.request import TrendReq
        p = TrendReq(hl="en-US", tz=300, requests_args={"headers": UA})
        p.build_payload(list(TRENDS), timeframe="today 5-y", geo="US")
        g = p.interest_over_time().drop(columns="isPartial")
        _store(g, "alt_trends")
    except Exception as e:  # Google rate-limits aggressively; keep last snapshot
        print(f"google trends skipped: {e}")
    print("alt data collected")


def _load(name):
    p = C.DATA / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def alt_signals() -> pd.DataFrame:
    """One row per indicator: latest value, change, z vs 5y history of that change,
    and the signed signal (positive = good for the mapped sectors)."""
    rows = []
    fred = _load("alt_fred")
    for sid, (label, tf, sign, sect, why) in ALT_FRED.items():
        s = fred[sid].dropna()
        m = s.resample("ME").last()
        if tf == "yoy":
            ch = m.pct_change(12, fill_method=None) * 100
        elif tf == "chg3":
            ch = m.diff(3)
        else:
            ch = m
        ch = ch.dropna()
        hist = ch.iloc[-61:-1]
        z = (ch.iloc[-1] - hist.mean()) / hist.std()
        rows.append({"Indicator": label, "Source": f"FRED {sid}", "Last obs": s.index[-1].date(),
                     "Latest": s.iloc[-1], "Change": ch.iloc[-1],
                     "Change type": {"yoy": "YoY %", "chg3": "3m chg", "lvl_z": "level"}[tf],
                     "z (5y)": z, "Signal": np.clip(sign * z, -3, 3), "Sectors": sect, "Why": why})
    tsa = _load("alt_tsa")
    if tsa is not None:
        s = tsa["tsa"].rolling(28).mean().dropna()
        last = s.index[-1]
        prev = s.asof(last - pd.DateOffset(years=1))
        yoy = (s.iloc[-1] / prev - 1) * 100
        yoy_hist = (s / s.shift(364) - 1).dropna() * 100
        z = (yoy - yoy_hist.iloc[-365:].mean()) / yoy_hist.iloc[-365:].std()
        rows.append({"Indicator": "TSA traveller throughput (28d avg)", "Source": "tsa.gov", "Last obs": last.date(),
                     "Latest": s.iloc[-1], "Change": yoy, "Change type": "YoY %", "z (5y)": z,
                     "Signal": np.clip(z, -3, 3), "Sectors": {"XLI": 1, "XLY": 1},
                     "Why": "airlines (XLI), travel & leisure (XLY)"})
    g = _load("alt_trends")
    if g is not None:
        for term, (sign, sect, why) in TRENDS.items():
            s = g[term].astype(float)
            lvl = s.iloc[-4:].mean()
            z = (lvl - s.iloc[:-4].mean()) / s.iloc[:-4].std()
            rows.append({"Indicator": f"Google Trends: '{term}'", "Source": "Google Trends (US, 5y)",
                         "Last obs": s.index[-1].date(), "Latest": lvl, "Change": np.nan,
                         "Change type": "4w avg vs 5y", "z (5y)": z, "Signal": np.clip(sign * z, -3, 3),
                         "Sectors": sect, "Why": why})
    return pd.DataFrame(rows)


def alt_sector_overlay(sig_tab: pd.DataFrame) -> pd.Series:
    """Average signed signal per sector across the indicators mapped to it."""
    acc = {s: [] for s in C.SECTORS}
    for _, r in sig_tab.iterrows():
        for s, w in r["Sectors"].items():
            acc[s].append(w * r["Signal"])
    return pd.Series({s: np.mean(v) if v else np.nan for s, v in acc.items()})
