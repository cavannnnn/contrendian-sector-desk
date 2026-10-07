"""Composite scoring, long/short selection and backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
import features as F

SECT = F.SECT


def monthly_returns() -> tuple[pd.DatetimeIndex, pd.DataFrame, pd.DataFrame]:
    px = F.load("px_adj")
    px = px[px.index < pd.Timestamp.today().normalize()]  # drop today's partial bar
    dates = F.month_ends(px.index)
    m = px.reindex(dates)
    ret = m.pct_change(fill_method=None)
    sect = ret[SECT]
    excess = sect.sub(sect.mean(axis=1), axis=0)  # vs equal-weight sector average
    return dates, ret, excess


def select(score: pd.Series, rsi: pd.Series) -> tuple[list[str], list[str]]:
    """Top/bottom N by score, skipping overbought longs / oversold shorts."""
    s = score.dropna().sort_values(ascending=False)
    longs = [t for t in s.index if not rsi.get(t, 50) > C.RSI_OVERBOUGHT][:C.N_LONG]
    shorts = [t for t in s.index[::-1] if not rsi.get(t, 50) < C.RSI_OVERSOLD and t not in longs][:C.N_SHORT]
    return longs, shorts


def build_signals():
    dates, ret, excess = monthly_returns()
    excess_fwd = excess.shift(-1)
    regimes = F.macro_regimes(dates)
    macro = F.macro_scores(regimes).reindex(dates)
    macro_learned = F.macro_scores_learned(regimes, excess_fwd).reindex(dates)
    tech_daily = F.technical_daily()
    tech = F.technical_scores(tech_daily, dates)
    value_hist = F.valuation_history_scores(dates)
    rsi_m = tech_daily["rsi"].reindex(dates, method="ffill")
    return dict(dates=dates, ret=ret, excess=excess, excess_fwd=excess_fwd, regimes=regimes,
                macro=macro, macro_learned=macro_learned, tech=tech, value_hist=value_hist, rsi=rsi_m, tech_daily=tech_daily)


def composite(macro, fund, tech, w=(C.W_MACRO, C.W_FUND, C.W_TECH)) -> pd.DataFrame:
    """Weighted sum of layer z-scores; a missing layer is dropped and the
    remaining weights renormalised (e.g. before XLC/XLRE existed)."""
    layers = [(macro, w[0]), (fund, w[1]), (tech, w[2])]
    num = sum(l.fillna(0) * wt for l, wt in layers)
    den = sum(l.notna() * wt for l, wt in layers)
    return F.xs_z(num / den.replace(0, np.nan))


def backtest(sig: dict, w=(C.W_MACRO, C.W_FUND, C.W_TECH), start=C.BACKTEST_START,
             hold=C.HOLD_MONTHS) -> dict:
    """Monthly signals, each month's 3-long/3-short book held for `hold` months
    (overlapping tranches). Fundamental layer in the backtest = valuation vs own
    history (the only fundamental signal with free point-in-time history)."""
    score = composite(sig["macro"], sig["value_hist"], sig["tech"], w)
    ret = sig["ret"]
    rows, tranches, prev_w = [], [], pd.Series(0.0, index=SECT)
    dates = [d for d in sig["dates"] if d >= pd.Timestamp(start)]
    for t, t_next in zip(dates[:-1], dates[1:]):
        longs, shorts = select(score.loc[t], sig["rsi"].loc[t])
        if not longs or not shorts:
            continue
        book = pd.Series(0.0, index=SECT)
        book[longs] = 1 / len(longs)
        book[shorts] = -1 / len(shorts)
        tranches = (tranches + [book])[-hold:]
        wts = sum(tranches) / len(tranches)
        r = ret.loc[t_next, SECT].fillna(0)
        turnover = (wts - prev_w).abs().sum()
        lw, plw = wts.clip(lower=0), prev_w.clip(lower=0)
        rows.append({"date": t_next,
                     "long_short": (wts * r).sum() - turnover * C.COST_BPS / 1e4,
                     "long_only": (lw * r).sum() / lw.sum() - (lw - plw).abs().sum() * C.COST_BPS / 1e4,
                     "eq_sectors": ret.loc[t_next, SECT].dropna().mean(),
                     "spy": ret.loc[t_next, C.BENCH], "turnover": turnover,
                     "longs": ",".join(longs), "shorts": ",".join(shorts)})
        prev_w = wts
    res = pd.DataFrame(rows).set_index("date")
    return {"returns": res, "score": score}


def signal_ic(sig: dict, start=C.BACKTEST_START) -> pd.DataFrame:
    """Mean cross-sectional Spearman IC of each signal vs forward sector excess
    returns at several horizons, with an overlap-adjusted t-stat."""
    td, d = sig["tech_daily"], sig["dates"]
    sigs = {"Macro (a-priori clock + rates)": sig["macro"],
            "Macro (data-fitted, not used)": sig["macro_learned"],
            "Valuation vs own history": sig["value_hist"], "Technical composite": sig["tech"],
            "12-1m relative momentum": td["mom_12_1"].reindex(d, method="ffill"),
            "Trend (ratio vs 200d)": td["trend"].reindex(d, method="ffill"),
            "Composite 40/30/30": composite(sig["macro"], sig["value_hist"], sig["tech"])}
    out = {}
    for h in [1, 3, 6]:
        fwd = np.log1p(sig["excess"]).rolling(h).sum().shift(-h)
        for name, s in sigs.items():
            s2 = s.loc[start:].iloc[:-h]
            v = pd.Series([s2.loc[t].corr(fwd.loc[t], method="spearman") for t in s2.index]).dropna()
            out.setdefault(name, {})[f"IC {h}m"] = v.mean()
            out[name][f"t-stat {h}m"] = v.mean() / v.std() * np.sqrt(len(v) / h)
    return pd.DataFrame(out).T


def perf_stats(r: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    cum = (1 + r).prod()
    ann = cum ** (12 / n) - 1
    vol = r.std() * np.sqrt(12)
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return {"Ann. return": ann, "Ann. vol": vol, "Sharpe (rf=0)": ann / vol if vol else np.nan,
            "Max drawdown": dd, "Hit rate": (r > 0).mean(), "Months": n}


def stats_table(res: pd.DataFrame) -> pd.DataFrame:
    cols = {"long_short": "L/S (3 long - 3 short)", "long_only": "Long top-3",
            "eq_sectors": "Equal-weight sectors", "spy": "SPY"}
    t = pd.DataFrame({v: perf_stats(res[k]) for k, v in cols.items()}).T
    t.loc["L/S (3 long - 3 short)", "Avg. monthly turnover"] = res["turnover"].mean()
    act = res["long_only"] - res["eq_sectors"]
    t.loc["Long top-3", "Info. ratio vs EW"] = act.mean() / act.std() * np.sqrt(12)
    return t


def layer_attribution(sig: dict) -> pd.DataFrame:
    tests = {"Composite 40/30/30": (0.4, 0.3, 0.3), "Macro only": (1, 0, 0),
             "Fundamental (valuation) only": (0, 1, 0), "Technical only": (0, 0, 1),
             "Equal 1/3 each": (1 / 3, 1 / 3, 1 / 3), "Macro 50 / Tech 50": (0.5, 0, 0.5),
             "Tech-heavy 20/20/60": (0.2, 0.2, 0.6)}
    out = {}
    for name, w in tests.items():
        r = backtest(sig, w)["returns"]
        s = perf_stats(r["long_short"])
        out[name] = {"L/S ann. return": s["Ann. return"], "L/S Sharpe": s["Sharpe (rf=0)"],
                     "L/S max DD": s["Max drawdown"],
                     "Long-only excess vs EW (ann.)": (r["long_only"] - r["eq_sectors"]).mean() * 12}
    return pd.DataFrame(out).T


def subperiod_stats(res: pd.DataFrame) -> pd.DataFrame:
    periods = {"2005-2009 (GFC)": ("2005", "2009"), "2010-2015 (ZIRP)": ("2010", "2015"),
               "2016-2019": ("2016", "2019"), "2020-2021 (COVID)": ("2020", "2021"),
               "2022-2023 (hiking)": ("2022", "2023"), "2024-now": ("2024", "2100")}
    out = {}
    for name, (a, b) in periods.items():
        sub = res.loc[a:b]
        if len(sub) > 3:
            s = perf_stats(sub["long_short"])
            out[name] = {"L/S ann. return": s["Ann. return"], "L/S Sharpe": s["Sharpe (rf=0)"],
                         "Long-only excess vs EW (ann.)": (sub["long_only"] - sub["eq_sectors"]).mean() * 12}
    return pd.DataFrame(out).T


def scenario_table(sig: dict) -> pd.DataFrame:
    """Historical average next-month excess return (annualised) of each sector in
    the regime implied by each scenario, plus the probability-weighted expectation."""
    reg, ef = sig["regimes"], sig["excess_fwd"]
    cols = {}
    for name, sc in C.SCENARIOS.items():
        mask = (reg["growth"] == sc["growth"]) & (reg["inflation"] == sc["inflation"]) & (reg["rates"] == sc["rates"])
        cols[f"{name} ({sc['prob']:.0%})"] = ef[mask].mean() * 12
    t = pd.DataFrame(cols)
    probs = np.array([sc["prob"] for sc in C.SCENARIOS.values()])
    t["Prob.-weighted"] = t.iloc[:, :len(probs)].fillna(0).values @ probs
    t.index = [f"{C.SECTORS[i]} ({i})" for i in t.index]
    return t.sort_values("Prob.-weighted", ascending=False)


def regime_heatmap_table(sig: dict) -> pd.DataFrame:
    reg, ef = sig["regimes"], sig["excess_fwd"]
    t = ef.groupby(reg["quadrant"]).mean().T * 12
    r2 = ef.groupby(reg["rates"]).mean().T * 12
    r2.columns = [f"Rates {c}" for c in r2.columns]
    t = pd.concat([t[["Recovery", "Overheat", "Stagflation", "Slowdown"]], r2], axis=1)
    t.index = [C.SECTORS[i] for i in t.index]
    return t


def live_scores(sig: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Latest scores with the full fundamental layer (valuation history + snapshot)."""
    fund = F.sector_fundamentals()
    snap = F.fundamental_snapshot_score(fund)
    t = sig["dates"][-1]
    vh = sig["value_hist"].loc[t]
    fund_score = F.xs_z((vh.fillna(0) / 3 + snap * 2 / 3).to_frame().T).iloc[0]
    tab = pd.DataFrame({
        "Sector": [C.SECTORS[s] for s in SECT],
        "Macro": sig["macro"].loc[t], "Fundamental": fund_score, "Technical": sig["tech"].loc[t],
        "Valuation vs own hist.": vh, "Fund. snapshot": snap,
        "RSI(14)": sig["rsi"].loc[t],
        "12-1m rel. mom.": sig["tech_daily"]["mom_12_1"].reindex([t], method="ffill").iloc[0],
    }, index=SECT)
    row = lambda c: tab[[c]].T.set_axis([t])
    tab["Composite"] = composite(row("Macro"), row("Fundamental"), row("Technical")).iloc[0]
    longs, shorts = select(tab["Composite"], tab["RSI(14)"])
    tab["Call"] = ["LONG" if s in longs else "SHORT" if s in shorts else "" for s in SECT]
    tab = tab.sort_values("Composite", ascending=False)
    tab.attrs["asof"] = t
    return tab, fund
