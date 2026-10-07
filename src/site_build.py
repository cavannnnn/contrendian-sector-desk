"""Exports every pipeline output to one JSON blob and injects it into site/template.html,
producing output/site/index.html (the integrated research site)."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

import alt_data as A
import config as C
import international as I
import model as M
import report as R


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (pd.Timestamp, date)):
        return str(o)[:10]
    return o


TAPE = [("SPX ETF", "SPY", "px"), ("NDX ETF", "QQQ", "px"), ("RUSSELL", "IWM", "px"), ("WTI", "CL=F", "px"),
        ("BRENT", "BZ=F", "px"), ("NAT GAS", "NG=F", "px"), ("GOLD", "GC=F", "px"), ("COPPER", "HG=F", "px"),
        ("UST 10Y", "^TNX", "yld"), ("DXY", "DX-Y.NYB", "px"), ("EURUSD", "EURUSD=X", "fx"), ("VIX", "^VIX", "px"),
        ("20Y+ UST", "TLT", "px"), ("HY CREDIT", "HYG", "px"), ("BTC", "BTC-USD", "px")]
CURVE = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30"]


def _curve():
    import io, requests
    out = {}
    for sid in CURVE:
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=20)
            out[sid] = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=".").iloc[:, 0].dropna()
        except Exception:
            return None
    df = pd.DataFrame(out).ffill().dropna()
    last = df.index[-1]
    pick = lambda d: df.loc[:d].iloc[-1]
    return {"tenors": ["1M", "3M", "6M", "1Y", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"],
            "now": pick(last).tolist(), "m1": pick(last - pd.DateOffset(months=1)).tolist(),
            "y1": pick(last - pd.DateOffset(years=1)).tolist(), "asof": str(last.date())}


def _market():
    px = pd.read_parquet(C.DATA / "px_adj.parquet")
    tape = []
    for label, t, kind in TAPE:
        s = px[t].dropna()
        if len(s) < 2:
            continue
        last, prev = s.iloc[-1], s.iloc[-2]
        if kind == "yld":  # ^TNX is quoted in % (older feeds quote x10); change in basis points
            scale = 1 if last < 20 else 0.1
            lv, chg = last * scale, (last - prev) * scale * 100
        else:
            lv, chg = last, last / prev - 1
        tape.append({"label": label, "t": t, "kind": kind, "last": lv, "chg": chg, "date": str(s.index[-1].date())})
    names = list(C.SECTORS) + [C.BENCH]
    rows = []
    rets = px[names].pct_change(fill_method=None)
    yr = rets.iloc[-252:]
    for t in names:
        s = px[t].dropna()
        lv = s.iloc[-1]
        back = lambda n: lv / s.iloc[-1 - n] - 1 if len(s) > n else None
        ytd = lv / s[s.index.year < s.index[-1].year].iloc[-1] - 1
        w52 = s.iloc[-252:]
        b = yr[t].cov(yr[C.BENCH]) / yr[C.BENCH].var()
        rows.append({"t": t, "name": C.SECTORS.get(t, "S&P 500"), "last": lv, "d1": back(1), "w1": back(5), "m1": back(21),
                     "m3": back(63), "ytd": ytd, "y1": back(252), "hi": w52.max(), "lo": w52.min(),
                     "vol": yr[t].std() * np.sqrt(252), "beta": b, "spark": s.iloc[-126::3].round(3).tolist()})
    corr = yr[list(C.SECTORS)].corr()
    return tape, rows, {"names": list(corr.index), "vals": corr.values.round(3).tolist()}


def build_data(sig: dict) -> dict:
    tab, fund = M.live_scores(sig)
    bt = M.backtest(sig)
    res = bt["returns"]
    _, scan = R.latest_news_scan()
    alt = A.alt_signals()
    tab["Alt"] = A.alt_sector_overlay(alt)
    regions = I.comparison(tab, sig["macro"].iloc[-1])
    reg = sig["regimes"]
    t = sig["dates"][-1]

    sectors = []
    for s in C.SECTORS:
        r = tab.loc[s]
        sectors.append({"t": s, "name": C.SECTORS[s], "macro": r.Macro, "fund": r.Fundamental, "tech": r.Technical,
                        "comp": r.Composite, "call": r.Call or "", "rsi": r["RSI(14)"], "mom": r["12-1m rel. mom."],
                        "valhist": r["Valuation vs own hist."], "snap": r["Fund. snapshot"], "alt": r.Alt,
                        "secular": C.SECULAR[s][0], "secular_why": C.SECULAR[s][1],
                        "fund_detail": fund.loc[s].to_dict()})

    macro_cols = {"dgs10": "10Y Treasury yield", "cpi_yoy": "CPI YoY", "ppi_yoy": "PPI YoY", "wti": "WTI crude",
                  "unrate": "Unemployment rate", "sentiment": "UMich sentiment", "curve": "10Y–2Y curve",
                  "baa_spread": "Baa–10Y credit spread", "fedfunds": "Fed funds rate"}
    units = {"dgs10": "%", "cpi_yoy": "%", "ppi_yoy": "%", "wti": "$", "unrate": "%", "sentiment": "",
             "curve": "pp", "baa_spread": "pp", "fedfunds": "%"}
    r19 = reg.loc["2019":]
    macro = [{"key": k, "label": v, "unit": units[k],
              "points": [[d, x] for d, x in zip(r19.index.strftime("%Y-%m"), r19[k].round(3)) if pd.notna(x)]}
             for k, v in macro_cols.items()]
    trail = reg[["growth_score", "inflation_score", "quadrant"]].dropna().iloc[-13:]

    rs = sig["tech_daily"]["rel_strength"]
    rs = rs[rs.index >= rs.index[-1] - pd.DateOffset(years=1)].iloc[::5]
    rel = {s: [[d, v] for d, v in zip(rs.index.strftime("%Y-%m-%d"), (rs[s] / rs[s].iloc[0] * 100).round(2))] for s in C.SECTORS}

    scen = M.scenario_table(sig)
    scen_cols = list(C.SCENARIOS)
    scen_rows = [{"sector": idx, "vals": [scen.iloc[i, j] for j in range(len(scen_cols))]} for i, idx in enumerate(scen.index)]

    tape, perf, corr = _market()
    hold = pd.read_parquet(C.DATA / "holdings.parquet").reset_index()
    holdings = {e: g.nlargest(6, "weight")[["ticker", "name", "weight"]].values.tolist() for e, g in hold.groupby("etf")}
    rh = reg.loc["2005":, ["quadrant", "rates"]].dropna()
    regime_hist = [[d.strftime("%Y-%m"), q, r] for d, (q, r) in rh.iterrows()]
    ff = sig["regimes"].loc["2019":, ["fedfunds", "dgs10", "dgs2"]].dropna()
    rates_hist = {"dates": list(ff.index.strftime("%Y-%m")), "ff": ff.fedfunds.tolist(), "y10": ff.dgs10.tolist(), "y2": ff.dgs2.tolist()}
    eq = res[["long_only", "eq_sectors", "long_short", "spy"]]
    stats = M.stats_table(res)
    data = {
        "asof": str(t.date()), "built": str(date.today()),
        "weights": {"macro": C.W_MACRO, "fund": C.W_FUND, "tech": C.W_TECH},
        "rsi_limits": [C.RSI_OVERSOLD, C.RSI_OVERBOUGHT],
        "regime": reg.iloc[-1][["growth_score", "inflation_score", "quadrant", "rates", "credit", "dgs10", "dgs2",
                                "curve", "fedfunds", "cpi_yoy", "ppi_yoy", "unrate", "sentiment", "wti"]].to_dict(),
        "trail": [{"d": d.strftime("%Y-%m"), "g": r.growth_score, "i": r.inflation_score, "q": r.quadrant}
                  for d, r in trail.iterrows()],
        "clock": C.CLOCK_MAP, "rates_map": C.RATES_MAP,
        "sectors": sectors, "macro": macro, "rel": rel,
        "notes": {k: {"conviction": v[0], "thesis": v[1], "wrong_if": v[2]} for k, v in C.CALL_NOTES.items()},
        "news": scan, "news_sources": json.loads(sorted((C.DATA / "news").glob("*.json"))[-1].read_text()).get("sources", []),
        "alt": [{"name": r.Indicator, "src": r.Source, "last": r["Last obs"], "latest": r.Latest, "chg": r.Change,
                 "chgType": r["Change type"], "z": r["z (5y)"], "sig": r.Signal, "sectors": r.Sectors, "why": r.Why}
                for _, r in alt.iterrows()],
        "regions": {"rows": list(regions.index), "cols": list(regions.columns), "vals": regions.values.tolist()},
        "scenarios": {"names": scen_cols, "probs": [C.SCENARIOS[s]["prob"] for s in scen_cols],
                      "defs": [C.SCENARIOS[s] for s in scen_cols], "rows": scen_rows},
        "regime_heat": (lambda h: {"rows": list(h.index), "cols": list(h.columns), "vals": h.values.tolist()})(M.regime_heatmap_table(sig)),
        "backtest": {"dates": list(eq.index.strftime("%Y-%m")), "long_only": eq.long_only.tolist(),
                     "eq": eq.eq_sectors.tolist(), "ls": eq.long_short.tolist(), "spy": eq.spy.tolist(),
                     "picks": [[d, l, s] for d, l, s in zip(res.index.strftime("%Y-%m"), res.longs, res.shorts)][-24:]},
        "stats": {k: v for k, v in stats.T.to_dict().items()},
        "subperiods": M.subperiod_stats(res).T.to_dict(),
        "ic": M.signal_ic(sig).T.to_dict(),
        "attribution": M.layer_attribution(sig).T.to_dict(),
        "tape": tape, "perf": perf, "corr": corr, "holdings": holdings, "regime_hist": regime_hist,
        "rates_hist": rates_hist, "curve": _curve(),
        "events": [{"date": d, "what": w, "sector": s_, "src": src} for d, w, s_, src in C.EVENTS],
        "alt_count": len(alt),
    }
    return _clean(data)


def build_site(sig: dict) -> str:
    data = build_data(sig)
    tpl = (C.ROOT / "site" / "template.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out = C.OUT / "site"
    out.mkdir(parents=True, exist_ok=True)
    (out / "artifact.html").write_text(html)  # body content only, for publishing as an Artifact
    (out / "index.html").write_text(          # standalone page for local use or any static host
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
        + html + "</body></html>")
    return str(out / "index.html")
