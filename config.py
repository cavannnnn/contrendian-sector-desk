"""Central configuration for the sector-rotation framework."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "output"
CHARTS = OUT / "charts"
DB_PATH = DATA / "sector_rotation.duckdb"

# GICS sectors -> SPDR Select Sector ETFs
SECTORS = {
    "XLE": "Energy",
    "XLB": "Materials",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLF": "Financials",
    "XLY": "Cons. Discretionary",
    "XLP": "Cons. Staples",
    "XLK": "Info. Technology",
    "XLC": "Comm. Services",
    "XLRE": "Real Estate",
}
BENCH = "SPY"
EXTRA_TICKERS = ["RSP", "HG=F", "GC=F", "CL=F", "BZ=F", "NG=F", "DX-Y.NYB", "^VIX", "^TNX", "QQQ", "IWM", "TLT", "HYG", "EURUSD=X", "BTC-USD"]  # cross-asset tape
PRICE_START = "1998-12-01"

# FRED series: id -> (description, publication lag in days)
FRED_SERIES = {
    "INDPRO": ("Industrial production", 45),
    "CPIAUCSL": ("CPI", 45),
    "PPIACO": ("PPI all commodities", 45),
    "UNRATE": ("Unemployment rate", 35),
    "ICSA": ("Initial jobless claims", 5),
    "UMCSENT": ("UMich consumer sentiment", 30),
    "FEDFUNDS": ("Fed funds rate", 5),
    "DGS10": ("10Y Treasury", 1),
    "DGS2": ("2Y Treasury", 1),
    "T10Y2Y": ("10Y-2Y spread", 1),
    "T5YIE": ("5Y breakeven inflation", 1),
    "DCOILWTICO": ("WTI crude", 1),
    "BAA10Y": ("Baa corporate - 10Y spread", 1),
    "GDPC1": ("Real GDP", 90),
}

# Model weights (round numbers on purpose, no in-sample optimisation)
W_MACRO, W_FUND, W_TECH = 0.40, 0.30, 0.30
N_LONG = N_SHORT = 3
RSI_OVERBOUGHT, RSI_OVERSOLD = 75, 25
COST_BPS = 10           # one-way transaction cost per unit turnover
BACKTEST_START = "2005-01-31"
MIN_REGIME_HISTORY = 36  # months of history before macro layer is trusted
SHRINK_K = 24            # shrinkage of regime-conditional means toward 0

HOLDINGS_TOP_N = 25      # top holdings per ETF used for bottom-up fundamentals

HOLD_MONTHS = 3          # overlapping tranches: each month's picks are held 3 months

# A-priori macro maps (fixed ex ante, NOT fitted to data).
# Investment clock: Greetham & Hartnett, "The Investment Clock", Merrill Lynch (Nov 2004),
# i.e. published before the 2005 backtest start.
CLOCK_MAP = {
    "Recovery":    {"XLK": 1, "XLY": 1, "XLF": 1, "XLC": 1, "XLI": .5, "XLU": -1, "XLP": -1, "XLV": -.5, "XLE": -.5},
    "Overheat":    {"XLE": 1, "XLB": 1, "XLI": 1, "XLF": .5, "XLU": -1, "XLP": -1, "XLRE": -.5, "XLK": -.5},
    "Stagflation": {"XLE": 1, "XLU": 1, "XLP": 1, "XLV": 1, "XLY": -1, "XLK": -1, "XLF": -1, "XLI": -.5, "XLRE": -.5},
    "Slowdown":    {"XLV": 1, "XLP": 1, "XLU": 1, "XLRE": 1, "XLE": -1, "XLB": -1, "XLI": -1, "XLY": -.5, "XLF": -.5},
}
# Rate environment: banks earn wider NIM and commodity producers hedge inflation when
# yields rise; long-duration "bond proxies" (utilities, REITs, staples) and long-duration
# growth equity suffer.
RATES_MAP = {
    "rising":  {"XLF": 1, "XLE": 1, "XLB": .5, "XLI": .5, "XLU": -1, "XLRE": -1, "XLP": -.5, "XLK": -.5},
    "falling": {"XLU": 1, "XLRE": 1, "XLP": .5, "XLK": .5, "XLF": -1, "XLE": -1, "XLB": -.5},
}
W_CLOCK, W_RATES = 2 / 3, 1 / 3

# Scenario probabilities (judgemental; edit freely). Updated 2026-10-07 after the news scan:
# Fed hiking into an oil shock with payrolls stalling tilts odds toward stagflation. Each scenario maps to a
# (growth, inflation, rates) regime used to look up historical sector behaviour.
SCENARIOS = {
    "Soft landing":   {"prob": 0.20, "growth": "up",   "inflation": "down", "rates": "falling"},
    "Reflation / AI capex boom": {"prob": 0.25, "growth": "up", "inflation": "up", "rates": "rising"},
    "Stagflation":    {"prob": 0.35, "growth": "down", "inflation": "up",   "rates": "rising"},
    "Recession":      {"prob": 0.20, "growth": "down", "inflation": "down", "rates": "falling"},
}

# Secular (10-40y) structural tailwind / headwind, judgemental, -2..+2, with rationale.
SECULAR = {
    "XLK": (2.0, "AI, cloud, digitisation of every industry"),
    "XLV": (1.5, "ageing demographics, GLP-1 / biotech innovation (offset: drug-price policy)"),
    "XLU": (1.0, "electrification + AI data-centre load; regulated rate-base growth"),
    "XLI": (1.0, "grid build-out, reshoring, defence re-armament, automation"),
    "XLC": (0.5, "digital advertising, streaming; mature telecom drag"),
    "XLF": (0.0, "fintech disruption vs. wealth accumulation of ageing savers"),
    "XLB": (0.0, "copper/lithium demand from electrification vs. commodity chemicals overcapacity"),
    "XLY": (0.0, "e-commerce growth vs. EV disruption of autos, ageing consumer"),
    "XLRE": (-0.5, "remote work hurts offices; data centres, towers, logistics offset"),
    "XLE": (-1.0, "energy transition caps long-run demand (offset: chronic upstream under-investment)"),
    "XLP": (-1.0, "GLP-1 volume loss in snacks/beverages, private-label share gains, low growth"),
}

# Desk notes per call (conviction, thesis, invalidation). Judgemental, reviewed weekly.
CALL_NOTES = {
    "XLE": ("High", "Only sector top-ranked on all three layers; forward P/E 13x, FCF yield 4.3%; war premium and refined-product squeeze",
            "Iran ceasefire or Hormuz reopens; WTI below $80; XLE/SPY below its 200-day average"),
    "XLV": ("Medium", "Defensive growth fits the stagflation quadrant; ROE 36%; ageing demographics",
            "Drug-price cuts spread beyond agreed deals; growth re-accelerates and money rotates to cyclicals"),
    "XLK": ("Medium-low, half size", "Strongest momentum (+20% vs SPY over 12m); ROE 59%, revenue +49%; AI capex intact",
            "10Y above 5.5% compresses multiples; RSI above 75; hyperscalers cut capex guidance"),
    "XLY": ("High", "Gasoline +43% y/y, sentiment near record low, 7.4% mortgages; worst sector YTD (−8.7%)",
            "Gasoline below $3.50/gal or a Fed pivot; tariff refunds lift retailers"),
    "XLRE": ("High", "Bond proxy facing a 5.3% 10Y; forward P/E 31x; weakest macro and technical scores",
             "10Y back below 4.75%; Fed pivot"),
    "XLU": ("Low, half size", "Debt-funded capex (FCF yield −9.5%) at 5%+ rates; rate-sensitive",
            "AI power demand re-rates the group (generation +7% y/y); swap the short to Materials (XLB)"),
}

# Upcoming catalysts shown on the site (each sourced from the news scan).
EVENTS = [
    ("2026-10-13", "Q3 bank earnings: JPM, GS, WFC, C", "XLF", "moneymorning.com, 25 Sep 2026"),
    ("2026-10-14", "Q3 bank earnings: BAC, MS", "XLF", "moneymorning.com, 25 Sep 2026"),
    ("2026-10-15", "Q3 earnings: USB, SCHW (approx.)", "XLF", "moneymorning.com, 25 Sep 2026"),
    ("2026-10-27", "FOMC meeting, Oct 27-28 (dots: one more 25bp hike in 2026)", "ALL", "fedratecalc.com; CNBC 16 Sep 2026"),
]
