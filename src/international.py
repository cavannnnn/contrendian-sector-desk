"""Cross-country extension: the same technical layer applied to global (iShares Global
sector ETFs vs ACWI) and European (iShares STOXX Europe 600 sector ETFs vs STOXX 600)
sector sets, mapped to the 11 GICS sectors. Macro layer reuses the US regime as a
proxy for the global cycle (a stated simplification); a region-specific regime
(OECD CLI, Eurostat HICP, ECB rates) is the upgrade path."""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

import config as C
import features as F
from collect import _store

REGIONS = {
    "Global": {"bench": "ACWI", "map": {"XLE": "IXC", "XLB": "MXI", "XLI": "EXI", "XLU": "JXI", "XLV": "IXJ",
                                         "XLF": "IXG", "XLY": "RXI", "XLP": "KXI", "XLK": "IXN", "XLC": "IXP",
                                         "XLRE": "REET"}},
    # ICB supersectors approximating GICS (Financials = banks, Discretionary = autos & parts)
    "Europe": {"bench": "EXSA.DE", "map": {"XLE": "EXH1.DE", "XLB": "EXV6.DE", "XLI": "EXH4.DE", "XLU": "EXH9.DE",
                                            "XLV": "EXV4.DE", "XLF": "EXV1.DE", "XLY": "EXV5.DE", "XLP": "EXH3.DE",
                                            "XLK": "EXV3.DE", "XLC": "EXV2.DE", "XLRE": "EXI5.DE"}},
}


def collect_international() -> None:
    tick = [t for r in REGIONS.values() for t in list(r["map"].values()) + [r["bench"]]]
    px = yf.download(tick, start="2005-01-01", auto_adjust=True, progress=False)["Close"]
    _store(px, "px_intl")


def region_scores(region: str, macro_today: pd.Series) -> pd.DataFrame:
    cfg = REGIONS[region]
    px = F.load("px_intl").ffill()
    px = px[px.index < pd.Timestamp.today().normalize()]
    b = px[cfg["bench"]]
    rows = {}
    for us, t in cfg["map"].items():
        ratio = (px[t] / b).dropna()
        macd = ratio.ewm(span=12).mean() - ratio.ewm(span=26).mean()
        rows[us] = {"ETF": t,
                    "mom_12_1": ratio.iloc[-22] / ratio.iloc[-253] - 1,
                    "trend": ratio.iloc[-1] / ratio.iloc[-200:].mean() - 1,
                    "macd": ((macd - macd.ewm(span=9).mean()) / ratio).iloc[-1],
                    "rsi": F.rsi(px[t].dropna()).iloc[-1],
                    "rel_12m": ratio.iloc[-1] / ratio.iloc[-253] - 1}
    df = pd.DataFrame(rows).T
    z = lambda s: ((s.astype(float) - s.astype(float).mean()) / s.astype(float).std()).clip(-3, 3)
    tech = z(0.5 * z(df.mom_12_1) + 0.3 * z(df.trend) + 0.2 * z(df.macd))
    df["Technical"] = tech
    df["Macro (US-regime proxy)"] = macro_today
    df["Composite"] = z(C.W_MACRO * df["Macro (US-regime proxy)"] + (1 - C.W_MACRO) * df["Technical"])
    df["Sector"] = [C.SECTORS[s] for s in df.index]
    return df.sort_values("Composite", ascending=False)


def comparison(us_table: pd.DataFrame, macro_today: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame({"US": us_table["Composite"]})
    for r in REGIONS:
        out[r] = region_scores(r, macro_today)["Composite"]
    out.index = [f"{C.SECTORS[s]}" for s in out.index]
    return out.sort_values("US", ascending=False)
