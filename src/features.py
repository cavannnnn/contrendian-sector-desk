"""Feature engineering for the three layers. All signals are point-in-time:
macro data are only used after their publication lag, and every standardisation
uses expanding (past-only) statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

SECT = list(C.SECTORS)


def load(name: str) -> pd.DataFrame:
    df = pd.read_parquet(C.DATA / f"{name}.parquet")
    if name.startswith("px_") and C.BENCH in df.columns:
        df = df[df[C.BENCH].notna()]  # US trading days only (crypto/FX on the tape trade weekends)
    return df


def month_ends(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each month present in the index."""
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby([idx.year, idx.month]).max().values)


def xs_z(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per row, clipped at +/-3."""
    z = df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)
    return z.clip(-3, 3)


def ts_z(s: pd.Series, min_periods: int = 36) -> pd.Series:
    """Expanding (past-only) time-series z-score."""
    return ((s - s.expanding(min_periods).mean()) / s.expanding(min_periods).std()).clip(-3, 3)


# ---------------------------------------------------------------- macro layer
def macro_panel() -> pd.DataFrame:
    """Daily point-in-time macro panel: each observation becomes visible only
    after its publication lag, then forward-filled."""
    fred = load("fred")
    cols = {}
    for sid, (_, lag) in C.FRED_SERIES.items():
        s = fred[sid].dropna()
        s.index = s.index + pd.Timedelta(days=lag)
        cols[sid] = s
    px = load("px_adj")
    cols["CU_AU"] = (px["HG=F"] / px["GC=F"]).dropna()
    daily = pd.DataFrame(cols).sort_index()
    daily = daily[~daily.index.duplicated()].ffill()
    return daily


def macro_regimes(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly growth / inflation / rates / credit regime at each date."""
    d = macro_panel()
    m = d.reindex(d.index.union(dates)).ffill().reindex(dates)

    def yoy(s):  # 12-month change on the monthly grid
        return s.pct_change(12, fill_method=None) * 100

    growth_parts = pd.DataFrame({
        "indpro": yoy(m["INDPRO"]).diff(3),
        "unrate": -m["UNRATE"].diff(3),
        "claims": -m["ICSA"].pct_change(3, fill_method=None) * 100,
        "sentiment": m["UMCSENT"].diff(3),
        "cu_au": m["CU_AU"].pct_change(3, fill_method=None) * 100,
    })
    infl_parts = pd.DataFrame({
        "cpi": yoy(m["CPIAUCSL"]).diff(3),
        "ppi": yoy(m["PPIACO"]).diff(3),
        "breakeven": m["T5YIE"].diff(3),
        "oil": m["DCOILWTICO"].pct_change(12, fill_method=None) * 100,
    })
    g = growth_parts.apply(ts_z).mean(axis=1)
    i = infl_parts.apply(ts_z).mean(axis=1)
    out = pd.DataFrame({
        "growth_score": g,
        "inflation_score": i,
        "growth": np.where(g > 0, "up", "down"),
        "inflation": np.where(i > 0, "up", "down"),
        "rates": np.where(m["DGS10"].diff(3) > 0, "rising", "falling"),
        "credit": np.where(m["BAA10Y"].diff(3) > 0, "widening", "tightening"),
        "dgs10": m["DGS10"], "dgs2": m["DGS2"], "curve": m["T10Y2Y"], "fedfunds": m["FEDFUNDS"],
        "cpi_yoy": yoy(m["CPIAUCSL"]), "ppi_yoy": yoy(m["PPIACO"]), "unrate": m["UNRATE"],
        "claims": m["ICSA"], "sentiment": m["UMCSENT"], "wti": m["DCOILWTICO"],
        "baa_spread": m["BAA10Y"], "breakeven5y": m["T5YIE"], "cu_au": m["CU_AU"],
        "indpro_yoy": yoy(m["INDPRO"]), "gdp_yoy": m["GDPC1"].pct_change(12, fill_method=None) * 100,
    }, index=dates)
    out.loc[g.isna(), "growth"] = None
    out.loc[i.isna(), "inflation"] = None
    quad = {("up", "down"): "Recovery", ("up", "up"): "Overheat",
            ("down", "up"): "Stagflation", ("down", "down"): "Slowdown"}
    out["quadrant"] = [quad.get((a, b)) for a, b in zip(out.growth, out.inflation)]
    return out


def regime_conditional(excess_fwd: pd.DataFrame, regime: pd.Series, asof: pd.Timestamp) -> pd.DataFrame:
    """Shrunk mean next-month excess return per sector for each regime value,
    using only (regime_t, return_t+1) pairs fully known at `asof`."""
    known = excess_fwd.index[excess_fwd.index < asof]  # fwd return of month t is realised at t+1 <= asof
    r, e = regime.reindex(known), excess_fwd.loc[known]
    rows = {}
    for val in r.dropna().unique():
        sub = e[r == val]
        n = sub.notna().sum()
        rows[val] = sub.mean() * n / (n + C.SHRINK_K)
    return pd.DataFrame(rows).T


def macro_scores(regimes: pd.DataFrame) -> pd.DataFrame:
    """Macro layer used in the model: a-priori investment-clock and rate-regime maps."""
    def mapped(col, mp):
        return pd.DataFrame([{s: mp.get(v, {}).get(s, 0) if isinstance(v, str) else np.nan for s in SECT}
                             for v in regimes[col]], index=regimes.index)
    raw = C.W_CLOCK * mapped("quadrant", C.CLOCK_MAP) + C.W_RATES * mapped("rates", C.RATES_MAP)
    return xs_z(raw)


def macro_scores_learned(regimes: pd.DataFrame, excess_fwd: pd.DataFrame) -> pd.DataFrame:
    """Alternative (diagnostic only — negative out-of-sample IC, so not used in the
    composite). For each month: average of the regime-conditional expected excess returns
    across the quadrant, rate and credit regimes; then cross-sectional z."""
    scores = {}
    for t in regimes.index:
        if (excess_fwd.index < t).sum() < C.MIN_REGIME_HISTORY:
            continue
        parts = []
        for col in ["quadrant", "rates", "credit"]:
            cur = regimes.at[t, col]
            if cur is None or pd.isna(cur):
                continue
            tab = regime_conditional(excess_fwd, regimes[col], t)
            if cur in tab.index:
                parts.append(tab.loc[cur])
        if parts:
            scores[t] = pd.concat(parts, axis=1).mean(axis=1)
    return xs_z(pd.DataFrame(scores).T.reindex(columns=SECT))


# ------------------------------------------------------------ technical layer
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def technical_daily() -> dict[str, pd.DataFrame]:
    px = load("px_adj")
    close, high, low, vol = load("px_close"), load("px_high"), load("px_low"), load("px_volume")
    feats = {k: {} for k in ["mom_12_1", "trend", "macd", "vwap", "rsi", "rel_strength"]}
    for t in SECT:
        p = px[t].dropna()
        ratio = (p / px[C.BENCH]).dropna()
        feats["rel_strength"][t] = ratio
        feats["mom_12_1"][t] = ratio.shift(21) / ratio.shift(252) - 1
        feats["trend"][t] = ratio / ratio.rolling(200).mean() - 1
        ema12, ema26 = ratio.ewm(span=12).mean(), ratio.ewm(span=26).mean()
        macd = ema12 - ema26
        feats["macd"][t] = (macd - macd.ewm(span=9).mean()) / ratio
        typical = (high[t] + low[t] + close[t]) / 3
        vwap20 = (typical * vol[t]).rolling(20).sum() / vol[t].rolling(20).sum()
        feats["vwap"][t] = close[t] / vwap20 - 1
        feats["rsi"][t] = rsi(p)
    return {k: pd.DataFrame(v) for k, v in feats.items()}


def technical_scores(tech: dict[str, pd.DataFrame], dates: pd.DatetimeIndex) -> pd.DataFrame:
    at = {k: v.reindex(dates, method="ffill") for k, v in tech.items()}
    score = (0.50 * xs_z(at["mom_12_1"]) + 0.25 * xs_z(at["trend"])
             + 0.15 * xs_z(at["macd"]) + 0.10 * xs_z(at["vwap"]))
    return xs_z(score)


# ---------------------------------------------------------- fundamental layer
def dividend_yield_history(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Trailing-12m dividend yield of each ETF on the monthly grid."""
    divs, close = load("dividends"), load("px_close")
    out = {}
    for t in SECT:
        d = divs[t].dropna() if t in divs else pd.Series(dtype=float)
        ttm = d.rolling("365D").sum().reindex(close.index, method="ffill")
        ttm[close.index < d.index.min() + pd.Timedelta(days=365)] = np.nan
        out[t] = (ttm / close[t]).reindex(dates, method="ffill")
    return pd.DataFrame(out)


def valuation_history_scores(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Valuation vs. each sector's OWN history: dividend-yield z-score over a
    trailing 10-year window (min 3y). Cheap vs own past -> positive. Backtestable."""
    dy = dividend_yield_history(dates)
    z = (dy - dy.rolling(120, min_periods=36).mean()) / dy.rolling(120, min_periods=36).std()
    return z.clip(-3, 3)


def sector_fundamentals() -> pd.DataFrame:
    """Bottom-up, weight-aggregated sector fundamentals from top ETF holdings."""
    hold = load("holdings").reset_index()
    f = load("fundamentals")
    df = hold.merge(f, left_on="ticker", right_index=True, how="left")
    rows = {}
    for etf, g in df.groupby("etf"):
        w = g["weight"]

        def wavg(col, lo=None, hi=None):
            x = pd.to_numeric(g[col], errors="coerce")
            if lo is not None:
                x = x.clip(lo, hi)
            m = x.notna()
            return float((x[m] * w[m]).sum() / w[m].sum()) if m.any() else np.nan

        def yield_of(col, lo=-1e9, hi=1e9):  # aggregate multiples as yields (handles negatives)
            x = pd.to_numeric(g[col], errors="coerce")
            m = x.notna() & (x != 0) & x.between(lo, hi)
            return float((w[m] / x[m]).sum() / w[m].sum()) if m.any() else np.nan

        mc = pd.to_numeric(g["marketCap"], errors="coerce")
        fcf = pd.to_numeric(g["freeCashflow"], errors="coerce")
        m = mc.notna() & fcf.notna()
        rows[etf] = {
            "P/E (ttm)": 1 / yield_of("trailingPE"),
            "P/E (fwd)": 1 / yield_of("forwardPE"),
            "P/B": 1 / yield_of("priceToBook", 0.1, 100),  # drops unit errors in feed
            "D/E (%)": wavg("debtToEquity", 0, 500),
            "ROE": wavg("returnOnEquity", -0.5, 1.0),
            "Div. yield (%)": wavg("dividendYield"),
            "FCF yield": float(fcf[m].sum() / mc[m].sum()) if m.any() else np.nan,
            "Rev. growth YoY": wavg("revenueGrowth", -0.5, 1.0),
            "EPS growth YoY": wavg("earningsGrowth", -1.0, 2.0),
            "Gross margin": wavg("grossMargins"),
            "Op. margin": wavg("operatingMargins", -0.5, 1),
            "Net margin": wavg("profitMargins", -0.5, 1),
            "Holdings coverage": float(w.sum()),
        }
    return pd.DataFrame(rows).T.reindex(SECT)


def fundamental_snapshot_score(fund: pd.DataFrame) -> pd.Series:
    """Cross-sectional value / quality / growth composite for the live snapshot."""
    z = lambda s: ((s - s.mean()) / s.std()).clip(-3, 3)
    value = (z(1 / fund["P/E (fwd)"]) + z(fund["FCF yield"])) / 2
    de = fund["D/E (%)"].copy()
    de[["XLF", "XLRE"]] = np.nan  # leverage is the business model there; neutral
    lev = z(-de).fillna(0)
    quality = (z(fund["ROE"]) + z(fund["Op. margin"]) + lev) / 3
    growth = (z(fund["Rev. growth YoY"]) + z(fund["EPS growth YoY"])) / 2
    return z(value + quality + growth)
