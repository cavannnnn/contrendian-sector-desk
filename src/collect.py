"""Data collection: prices (yfinance), macro (FRED), ETF holdings (SSGA), fundamentals (yfinance).

Every collector writes a parquet snapshot into data/ and a table into DuckDB so each
weekly run is reproducible.
"""
from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import duckdb
import pandas as pd
import requests
import yfinance as yf

import config as C

UA = {"User-Agent": "Mozilla/5.0 (research; sector-rotation)"}


def _store(df: pd.DataFrame, name: str) -> None:
    C.DATA.mkdir(exist_ok=True)
    df.to_parquet(C.DATA / f"{name}.parquet")
    with duckdb.connect(str(C.DB_PATH)) as con:
        flat = df.reset_index()
        flat.columns = [str(c) for c in flat.columns]
        con.register("tmp", flat)
        con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM tmp')


def collect_prices() -> None:
    tickers = list(C.SECTORS) + [C.BENCH] + C.EXTRA_TICKERS
    raw = yf.download(tickers, start=C.PRICE_START, auto_adjust=False, progress=False, threads=True)
    _store(raw["Adj Close"], "px_adj")
    _store(raw["Close"], "px_close")
    _store(raw["Volume"], "px_volume")
    _store(raw["High"], "px_high")
    _store(raw["Low"], "px_low")
    divs = {}
    for t in list(C.SECTORS) + [C.BENCH]:
        d = yf.Ticker(t).dividends
        if len(d):
            d.index = d.index.tz_localize(None)
            divs[t] = d
    _store(pd.DataFrame(divs).sort_index(), "dividends")
    print(f"prices: {raw.index[0].date()} -> {raw.index[-1].date()}")


def collect_fred() -> None:
    out = {}
    for sid in C.FRED_SERIES:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        for attempt in range(3):
            try:
                r = requests.get(url, headers=UA, timeout=30)
                r.raise_for_status()
                break
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"FRED download failed: {sid}")
        s = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=".").iloc[:, 0]
        out[sid] = s.astype(float)
    df = pd.DataFrame(out).sort_index()
    _store(df, "fred")
    print(f"fred: {len(out)} series, last obs {df.index[-1].date()}")


def collect_holdings() -> None:
    rows = []
    for etf in C.SECTORS:
        url = ("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/"
               f"etfs/us/holdings-daily-us-en-{etf.lower()}.xlsx")
        r = requests.get(url, headers=UA, timeout=30, allow_redirects=True)
        r.raise_for_status()
        h = pd.read_excel(io.BytesIO(r.content), skiprows=4)
        h = h[pd.to_numeric(h["Weight"], errors="coerce").notna()]
        h = h[h["Ticker"].astype(str).str.match(r"^[A-Z.]+$")]
        h = h.sort_values("Weight", ascending=False).head(C.HOLDINGS_TOP_N)
        rows.append(pd.DataFrame({"etf": etf, "ticker": h["Ticker"].str.replace(".", "-", regex=False),
                                  "name": h["Name"], "weight": h["Weight"].astype(float) / 100}))
    df = pd.concat(rows, ignore_index=True)
    _store(df.set_index("etf"), "holdings")
    print(f"holdings: {len(df)} rows, coverage by ETF:\n{df.groupby('etf').weight.sum().round(2).to_dict()}")


FUND_FIELDS = ["trailingPE", "forwardPE", "priceToBook", "debtToEquity", "returnOnEquity",
               "dividendYield", "freeCashflow", "marketCap", "revenueGrowth", "earningsGrowth",
               "grossMargins", "operatingMargins", "profitMargins", "trailingEps", "forwardEps"]


def _info(ticker: str) -> dict:
    for attempt in range(3):
        try:
            inf = yf.Ticker(ticker).info
            return {"ticker": ticker, **{k: inf.get(k) for k in FUND_FIELDS}}
        except Exception:  # yfinance raises a variety of errors on throttling
            time.sleep(3 * (attempt + 1))
    return {"ticker": ticker}


def collect_fundamentals() -> None:
    hold = pd.read_parquet(C.DATA / "holdings.parquet").reset_index()
    tickers = sorted(hold.ticker.unique())
    with ThreadPoolExecutor(max_workers=6) as ex:
        data = list(ex.map(_info, tickers))
    df = pd.DataFrame(data).set_index("ticker")
    df["asof"] = str(date.today())
    _store(df, "fundamentals")
    # keep a dated history so valuation can later be compared with its own past
    hist = C.DATA / "fundamentals_history"
    hist.mkdir(exist_ok=True)
    df.to_parquet(hist / f"{date.today()}.parquet")
    print(f"fundamentals: {df['marketCap'].notna().sum()}/{len(df)} tickers with data")


def collect_all() -> None:
    collect_prices()
    collect_fred()
    collect_holdings()
    collect_fundamentals()


if __name__ == "__main__":
    collect_all()
