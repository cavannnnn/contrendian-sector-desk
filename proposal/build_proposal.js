// Builds the Project 1 proposal (.docx): 3-page core + appendix.
// Run: NODE_PATH=<dir with docx installed> node proposal/build_proposal.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, BorderStyle, ShadingType, LevelFormat, PageBreak, Footer, PageNumber,
  FootnoteReferenceRun, HeadingLevel, VerticalAlign,
} = require("docx");

const ROOT = path.join(__dirname, "..");
const CH = (f) => path.join(ROOT, "output", "charts", f);
const W = 10512;              // content width in DXA (Letter, 0.6" margins)
const PX = 701;               // same width in px @96dpi
const FONT = "Calibri";
const INK = "1F1F1D", INK2 = "52514E", BLUE = "2A78D6", RED = "C8312F", BAND = "DCEBF8", RULE = "8A8984";

// ---------- helpers
const t = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 18, bold: o.bold, italics: o.italics,
  color: o.color || INK, superScript: o.sup });
const fn = (id) => new FootnoteReferenceRun(id);
const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs, o)],
  spacing: { before: o.before || 0, after: o.after ?? 60, line: o.line || 252 }, alignment: o.align,
  numbering: o.bullet ? { reference: "bul", level: 0 } : undefined, keepNext: o.keepNext });
const h = (text, o = {}) => new Paragraph({ children: [t(text, { bold: true, size: o.size || 21, color: o.color || INK })],
  spacing: { before: o.before ?? 100, after: 50 }, keepNext: true,
  heading: o.level, border: o.rule ? { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 2 } } : undefined });
const img = (file, widthPx, ratio, o = {}) => new Paragraph({ alignment: o.align || AlignmentType.CENTER,
  spacing: { before: 20, after: o.after ?? 20 }, keepNext: o.keepNext,
  children: [new ImageRun({ type: "png", data: fs.readFileSync(CH(file)),
    transformation: { width: widthPx, height: Math.round(widthPx * ratio) },
    altText: { title: file, description: o.alt || file, name: file } })] });
const cap = (text) => p([t(text, { size: 15, italics: true, color: INK2 })], { after: 80 });
const bullet = (runs) => p(Array.isArray(runs) ? runs : [t(runs)], { bullet: true, after: 30 });

const thin = { style: BorderStyle.SINGLE, size: 4, color: "C9C8C3" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function table(widths, rows, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0 && !o.noHeader, cantSplit: true,
      children: r.map((c, j) => {
        const isHead = i === 0 && !o.noHeader;
        const runs = (Array.isArray(c) ? c : [c]).map((x) => typeof x === "string"
          ? t(x, { size: o.size || 15, bold: isHead, color: isHead ? INK : (o.colColor && o.colColor(i, j, x)) || INK }) : x);
        return new TableCell({ width: { size: widths[j], type: WidthType.DXA },
          borders: o.borderless ? { top: none, bottom: none, left: none, right: none }
            : { top: thin, bottom: thin, left: none, right: none },
          shading: isHead ? { fill: BAND, type: ShadingType.CLEAR, color: "auto" } : undefined,
          margins: { top: 30, bottom: 30, left: 60, right: 60 }, verticalAlign: o.vAlign || VerticalAlign.CENTER,
          children: [new Paragraph({ children: runs, spacing: { after: 0, line: 230 } })] });
      }) })) });
}
// side-by-side layout: [left children, right children] in a borderless 2-col table
function twoCol(left, right, lw) {
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [lw, W - lw],
    rows: [new TableRow({ children: [left, right].map((ch, j) => new TableCell({
      width: { size: j ? W - lw : lw, type: WidthType.DXA }, borders: { top: none, bottom: none, left: none, right: none },
      margins: { left: j ? 120 : 0, right: j ? 0 : 60 }, verticalAlign: VerticalAlign.TOP, children: ch })) })] });
}
const callColor = (i, j, x) => (j === 0 ? (x === "LONG" ? BLUE : RED) : undefined);

// ---------- footnotes (sources)
const FN = {
  1: "Fed raised the target range 25bp to 3.75-4.00% on 16 Sep 2026; median dot implies one more hike in 2026. CNBC, 16 Sep 2026; JPMorgan AM FOMC note.",
  2: "10Y Treasury touched 5.34%, highest since 2002 (Bloomberg, 1 & 5 Oct 2026). FRED DGS10 close 5.31% on 5 Oct 2026.",
  3: "US-Iran war since Feb 2026; Hormuz disruption, third US carrier deployed (CNBC, 1 Oct 2026). China halted October fuel exports; Russia diesel ban (EnergyNow, Oct 2026). FRED DCOILWTICO $96.16 (29 Sep).",
  4: "Sep payrolls +29k vs 84k expected; July revised to -10k; AHE +3.0% y/y (CNBC, 2 Oct 2026). Aug CPI +3.4% y/y, core 2.4%, gasoline +27% y/y (BLS / CNBC, 11 Sep 2026).",
  5: "UMich sentiment second-lowest on record in Sep 2026 (CNN, 25 Sep 2026). 30Y mortgage 7.28-7.44% (Freddie Mac PMMS / Money.com, 1-6 Oct 2026).",
  6: "September 2026: XLK +5.1%, the only sector up; Materials -7.6%. YTD: Energy +38.9%, Discretionary -8.7% (24/7 Wall St., 1 Oct 2026; Nasdaq Sep review).",
  7: "Hyperscaler 2026 capex ~$600-690bn (CreditSights via EnkiAI); US utilities ~$1.4tn capex plan to 2030 (Tech-Insider). FRED IPG2211S +7.0% y/y (Aug 2026).",
  8: "Greetham & Hartnett, 'The Investment Clock', Merrill Lynch, Nov 2004: published before the 2005 backtest start, so the mapping is not fitted to our sample.",
  9: "Supreme Court struck down IEEPA tariffs, 20 Feb 2026 (SCOTUSblog); Section 232/301 tariffs remain. MFN drug-pricing deals with 17 manufacturers (White House CEA, May 2026).",
};
const footnotes = Object.fromEntries(Object.entries(FN).map(([k, v]) => [k, { children: [new Paragraph({ children: [t(v, { size: 14, color: INK2 })] })] }]));

// ---------- PAGE 1
const page1 = [
  p([t("Contrendian ◦ Project 1", { size: 30, bold: true })], { align: AlignmentType.CENTER, after: 0 }),
  p([t("Sector Rotation & Long/Short Allocation: Proposal", { size: 22, color: INK2 })], { align: AlignmentType.CENTER, after: 20 }),
  p([t("Data as of 6 Oct 2026 · 11 US GICS sectors via SPDR ETFs · same framework run on Global & Europe sector sets", { size: 15, italics: true, color: INK2 })],
    { align: AlignmentType.CENTER, after: 100 }),
  h("Executive summary", { rule: true, before: 0 }),
  bullet([t("Regime: stagflation-leaning, rising rates. ", { bold: true }),
    t("The Fed hiked to 3.75-4.00%"), fn(1), t(", the 10Y hit a 24-year high of 5.3%"), fn(2),
    t(", WTI is ~$96 on the US-Iran war"), fn(3), t(", while payrolls stall (+29k) and wage growth slows"), fn(4),
    t(". Our growth-momentum composite just turned negative (-0.06) as inflation momentum turned positive (+0.19).")]),
  bullet([t("Call (3-month horizon, reviewed weekly): ", { bold: true }),
    t("LONG ", { bold: true, color: BLUE }), t("Energy, Health Care, Info. Technology; "),
    t("SHORT ", { bold: true, color: RED }), t("Cons. Discretionary, Real Estate, Utilities.")]),
  bullet([t("Robustness: ", { bold: true }), t("Energy ranks #1 and Real Estate / Discretionary rank #10-11 in the US, Global and Europe sector sets alike. "),
    t("Honest caveat: ", { bold: true }), t("the composite's historical edge is modest and regime-dependent: it paid in macro-driven periods (2005-09, 2022-23) and lost when mega-cap secular trends dominated (2016-19, 2024-26). We therefore size by conviction and pre-commit exit triggers.")]),
  table([780, 1700, 760, 1050, 3500, 2722], [
    ["Call", "Sector (ETF)", "Score z", "Conviction", "Thesis", "We are wrong if…"],
    ["LONG", "Energy (XLE)", "+2.25", "High", "Only sector top-ranked on all three layers; fwd P/E 13x, FCF yield 4.3%; war premium + refined-product squeeze", "Iran ceasefire / Hormuz reopens; WTI < $80; XLE/SPY < 200d"],
    ["LONG", "Health Care (XLV)", "+0.81", "Medium", "Defensive growth fits the stagflation quadrant; ROE 36%; ageing demographics (secular +1.5)", "MFN price cuts widen; growth re-accelerates and money rotates to cyclicals"],
    ["LONG", "Info. Tech. (XLK)", "+0.51", "Med-low (½ size)", "Strongest momentum (+20% vs SPY, 12m); ROE 59%, revenue +49%; AI capex intact", "10Y > 5.5% compresses multiples; RSI > 75; hyperscaler capex guide-down"],
    ["SHORT", "Cons. Disc. (XLY)", "−1.23", "High", [t("Gasoline +43% y/y, sentiment near record low, 7.4% mortgages", { size: 15 }), fn(5), t("; worst sector YTD (−8.7%)", { size: 15 }), fn(6)], "Gas < $3.50/gal or Fed pivot; tariff refunds lift retailers"],
    ["SHORT", "Real Estate (XLRE)", "−1.18", "High", "Bond proxy into a 5.3% 10Y; fwd P/E 31x; weakest macro + technical scores", "10Y < 4.75% / Fed pivot"],
    ["SHORT", "Utilities (XLU)", "−0.69", "Low (½ size)", "Debt-funded capex (FCF yield −9.5%) at 5%+ rates; rate-sensitive", "AI power demand re-rates the group (generation +7% y/y): swap to Materials (XLB)"],
  ], { colColor: callColor }),
  p("", { after: 40 }),
  img("00_framework.png", PX - 20, 0.354, { alt: "Framework: data pipeline feeding macro, fundamental and technical layers into a composite, overlay and book" }),
  cap("Figure 1. Framework. Three scored layers (weights fixed ex ante, not optimised) → composite z → qualitative overlay (max one notch, written reason) → book."),
];

// ---------- PAGE 2
const page2 = [
  new Paragraph({ children: [new PageBreak()] }),
  h("1. Evidence behind the six calls", { rule: true, before: 0 }),
  twoCol([
    img("01_sector_scores.png", 400, 0.564, { align: AlignmentType.LEFT, alt: "Heatmap of macro, fundamental, technical and composite scores for 11 sectors" }),
    cap("Figure 2. Layer scores (cross-sectional z)."),
  ], [
    p([t("Macro (40%). ", { bold: true }), t("Growth × inflation momentum places us in the "), t("Stagflation", { bold: true }),
      t(" quadrant of the Investment Clock"), fn(8), t(" (favours Energy, Health Care, Staples, Utilities) with "), t("rising rates", { bold: true }),
      t(" (favours Financials/Energy, penalises Utilities, Real Estate, long-duration Tech).")], { after: 50 }),
    p([t("Fundamental (30%). ", { bold: true }), t("Bottom-up from top-25 holdings: Energy combines the cheapest forward P/E (13x) with 39% revenue growth; Tech has the highest ROE/margins; Utilities have the worst FCF (−9.5% yield).")], { after: 50 }),
    p([t("Technical (30%). ", { bold: true }), t("12-1m relative momentum leads: Energy +27%, Tech +14%; Discretionary −16%, Utilities −15%. RSI blocks longs above 75 (Tech is at 72).")], { after: 50 }),
    p([t("Conflict worth naming: ", { bold: true }), t("Tech scores −1.40 on macro but +2.02 on technicals. We keep it (ranked #3) at half size; the secular case (Figure 4) supports holding through rate noise.")], { after: 0 }),
  ], 5900),
  h("2. Second- and third-order effects", { size: 19, before: 80 }),
  img("08_second_order_map.png", 490, 0.57, { alt: "Transmission map from three shocks to first- and second-order sector effects" }),
  cap("Figure 3. Transmission map of the three live shocks. The shorts are second-order victims of the same forces that drive the longs: oil → gas prices → discretionary wallets; yields → mortgages → housing-linked spend."),
  twoCol([
    img("09_secular_vs_cyclical.png", 310, 0.708, { align: AlignmentType.LEFT, alt: "Scatter of secular vs cyclical score per sector" }),
    cap("Figure 4. Secular (10-40y) vs cyclical (1-7y)."),
  ], [
    h("3. Secular vs cyclical", { size: 19, before: 0 }),
    bullet([t("Tech and Health Care sit in the top-right: structural tailwinds (AI, ageing) plus a positive cycle, so these are core longs.")]),
    bullet([t("Energy is "), t("tactical only", { bold: true }), t(": the cycle is strong but the energy transition is a long-run headwind. Trade it with a stop and don't own it.")]),
    bullet([t("Utilities are the tension: secular tailwind (electrification, AI load"), fn(7), t(") vs cyclical headwind (rates, negative FCF). Hence a low-conviction, half-size short with a pre-defined swap into Materials.")]),
    h("Unconventional associations (Appendix D)", { size: 17, before: 60 }),
    bullet([t("US power generation +7% y/y (z = +1.8) and Google 'data center' searches (z = +1.1): an AI-load signal for Utilities/Industrials.")]),
    bullet([t("Gasoline +43% y/y vs TSA throughput −1.8% y/y: fuel is crowding out travel (airlines, leisure).")]),
    bullet([t("'Ozempic' searches below their 5y average: a GLP-1 read-through for snack volumes (XLP) and pharma (XLV).")]),
  ], 4900),
];

// ---------- PAGE 3
const page3 = [
  new Paragraph({ children: [new PageBreak()] }),
  h("4. Scenario analysis", { rule: true, before: 0 }),
  twoCol([
    img("06_scenarios.png", 420, 0.507, { align: AlignmentType.LEFT, alt: "Heatmap of sector excess returns by scenario" }),
    cap("Figure 5. Historical annualised sector excess return in each scenario's regime (2000-26); probabilities are our judgement after the Oct-2026 news scan."),
  ], [
    p([t("Probabilities: stagflation 35%, reflation / AI boom 25%, soft landing 20%, recession 20%.", { bold: true })], { after: 50 }),
    bullet([t("Real Estate, Utilities and Staples are negative in the probability-weighted column: the shorts are robust across scenarios.")]),
    bullet([t("Tech is positive in 3 of 4 scenarios; only reflation (rates up) hurts, which matches our half-size stance.")]),
    bullet([t("Cross-check, not a sizing input: these data-fitted regime averages disagree with our calls on Discretionary (+4.0% weighted) and Health Care (−2.2%), and are flat on Energy. The same method had negative out-of-sample IC (Appendix C), so we note the disagreement and keep the Clock. A ceasefire (soft landing) is the main risk to the XLE long and the XLY short.")]),
  ], 6150),
  h("5. Backtest (2005-2026, monthly, 3-month overlapping holds, 10bp costs)", { size: 19, before: 60 }),
  twoCol([
    img("03_backtest.png", 400, 0.597, { align: AlignmentType.LEFT, alt: "Backtest equity curves and drawdowns" }),
  ], [
    table([1700, 800, 700, 800, 900], [
      ["Strategy", "Ann. ret", "Sharpe", "Max DD", "Hit rate"],
      ["L/S 3 vs 3", "−0.4%", "−0.03", "−46%", "49%"],
      ["Long top-3", "9.5%", "0.66", "−33%", "64%"],
      ["Equal-wt sectors", "10.1%", "0.70", "−49%", "67%"],
      ["SPY", "11.1%", "0.75", "−51%", "67%"],
    ], { size: 15 }),
    p("", { after: 40 }),
    p([t("Reading it honestly: ", { bold: true }), t("long/short is flat over the full sample but earned +4.5% p.a. in 2005-09 and +9.1% in the 2022-23 hiking cycle, the regime most similar to today. The long book cut the max drawdown from −49% to −33%. Signal ICs are positive but individually insignificant (|t| < 1.1), so the framework is a disciplined prior, not an alpha engine.", { size: 17 })], { after: 0 }),
  ], 5900),
  h("6. Limitations: exogenous shocks and model risk", { size: 19, before: 80 }),
];
// fix row with footnote ref
page3.push(table([2300, 8212], [
  ["Risk", "Impact and mitigation"],
  ["Geopolitical (Iran / Hormuz)", "Ceasefire unwinds the oil premium fast (hits XLE long, helps XLY short cover). Mitigation: WTI < $80 and 200d stops; weekly news-agent review."],
  ["Monetary / fiscal", [t("Deficits and tariff refunds (>$200bn)", { size: 15 }), fn(9), t(" add Treasury supply; a Fed pivot would hurt the XLRE / XLU shorts. Mitigation: 10Y < 4.75% trigger.", { size: 15 })]],
  ["Policy / regulatory", "MFN drug pricing (XLV); antitrust and AI export controls (XLK/XLC). Mitigation: half-size XLK; diversified XLV exposure."],
  ["Concentration", "XLK's top three holdings are ~40% of the ETF: a Tech long is largely an NVDA/AAPL/MSFT view. Alternative: equal-weight sector ETFs (RSPT)."],
  ["Data & model", "Macro data are latest-vintage (revisions not replayed); no free point-in-time fundamentals for the backtest; XLRE (2015) and XLC (2018) have short histories; weights are fixed, not optimised."],
], { size: 15 }));

// ---------- APPENDIX
const A = (title) => h(title, { rule: true, before: 120 });
const appendix = [
  new Paragraph({ children: [new PageBreak()] }),
  p([t("Appendix", { size: 26, bold: true })], { after: 60 }),
  A("A. Methodology and indicator definitions"),
  table([2100, 5612, 2800], [
    ["Layer / item", "Definition", "Source"],
    ["Growth momentum", "Mean expanding z of 3m changes: IP y/y, −unemployment, −jobless claims, UMich sentiment, copper/gold ratio", "FRED INDPRO, UNRATE, ICSA, UMCSENT; COMEX HG/GC"],
    ["Inflation momentum", "Mean expanding z of: CPI y/y Δ3m, PPI y/y Δ3m, 5y breakeven Δ3m, WTI y/y", "FRED CPIAUCSL, PPIACO, T5YIE, DCOILWTICO"],
    ["Macro score", "2/3 Investment-Clock map for the quadrant + 1/3 rate map (10Y 3m change sign); publication lags 1-90 days applied", "Greetham & Hartnett (2004)"],
    ["Fundamental (live)", "2/3 cross-sectional value (fwd earnings yield, FCF yield), quality (ROE, op. margin, −D/E ex-Fin/RE), growth (revenue, EPS y/y) + 1/3 div. yield z vs own 10y", "SSGA holdings + yfinance; ETF dividends"],
    ["Fundamental (backtest)", "Trailing-12m dividend yield z-score vs the sector's own 10y window (only free point-in-time valuation)", "yfinance dividends"],
    ["Technical", "50% 12-1m relative momentum vs SPY, 25% ratio vs 200d SMA, 15% MACD(12,26,9) on ratio, 10% price vs 20d VWAP; RSI(14) >75 / <25 filter", "yfinance OHLCV"],
    ["Portfolio", "Top/bottom 3 equal weight; monthly signal held 3 months in overlapping tranches; 10bp per unit turnover", ""],
  ], { size: 14 }),
  A("B. Data sources"),
  table([2600, 7912], [
    ["Public (used)", "Coverage"],
    ["yfinance", "SPDR ETF OHLCV and dividends since 1998; iShares Global and STOXX Europe 600 sector ETFs; constituent fundamentals"],
    ["FRED (St. Louis Fed)", "29 macro and alternative series (rates, inflation, labour, housing, power generation, capex orders, credit, USD, VIX)"],
    ["SSGA", "Daily SPDR holdings (top-25 per ETF, 64-100% weight coverage)"],
    ["TSA, Google Trends", "Daily air-traveller throughput; US search interest (recession, layoffs, gas prices, Ozempic, data center)"],
    ["Fed / EIA RSS + web news", "Policy and energy headlines feeding the Claude news agent (structured shocks, 2nd-order effects, sector sentiment)"],
  ], { size: 14 }),
  p("", { after: 40 }),
  table([2600, 7912], [
    ["Proprietary (suggested)", "Why it would help"],
    ["I/B/E/S or FactSet estimates", "Earnings-revision breadth: the most robust sector signal missing from free data"],
    ["Bloomberg / Compustat point-in-time", "Historical P/E, ROE, margins without look-ahead, so the full fundamental layer can be backtested"],
    ["ALFRED vintages (free, API key)", "Replays macro data as first published, removing revision bias"],
    ["EPFR fund flows, CFTC positioning", "Crowding and contrarian signals for sector ETFs"],
    ["Card-spend (e.g. Bloomberg Second Measure), satellite, freight (DAT, Baltic)", "Real-time read of consumer and goods activity ahead of official prints"],
  ], { size: 14 }),
  A("C. Backtest diagnostics"),
  table([3300, 900, 900, 900, 900, 900, 900], [
    ["Signal (Spearman IC vs fwd excess return)", "IC 1m", "t 1m", "IC 3m", "t 3m", "IC 6m", "t 6m"],
    ["Macro: a-priori Clock + rates (used)", "0.011", "0.38", "0.050", "0.99", "0.040", "0.57"],
    ["Macro: data-fitted regime means (rejected)", "−0.026", "−1.07", "−0.024", "−0.58", "−0.048", "−0.80"],
    ["Valuation vs own history", "−0.006", "−0.25", "0.008", "0.19", "0.020", "0.34"],
    ["Technical composite", "0.020", "0.73", "0.006", "0.14", "0.029", "0.46"],
    ["Composite 40/30/30", "0.011", "0.41", "0.037", "0.80", "0.042", "0.62"],
  ], { size: 14 }),
  p("", { after: 40 }),
  table([3300, 1800, 1800, 1800, 1812], [
    ["Sub-period", "L/S ann. return", "L/S Sharpe", "Long excess vs EW", "Note"],
    ["2005-09 (GFC)", "+4.5%", "0.51", "+1.2%", "macro-driven"],
    ["2010-15 (ZIRP)", "−1.8%", "−0.24", "−2.7%", ""],
    ["2016-19", "−4.2%", "−0.47", "−5.0%", "mega-cap growth"],
    ["2020-21 (COVID)", "0.0%", "0.00", "−0.2%", ""],
    ["2022-23 (hiking)", "+9.1%", "0.68", "+9.8%", "closest analogue"],
    ["2024-now", "−6.6%", "−0.66", "−0.6%", "AI concentration"],
  ], { size: 14 }),
  p([t("Layer attribution (L/S Sharpe): macro-only 0.06, technical-only −0.03, valuation-only −0.07, macro 50 / tech 50 0.06, composite −0.03. No weight set is significantly better; weights stay fixed at 40/30/30 to avoid overfitting.", { size: 15, color: INK2 })], { before: 40 }),
  A("D. Supporting charts"),
  img("04_macro_dashboard.png", 560, 0.684, { alt: "Macro dashboard of nine indicators since 2019" }),
  cap("Figure A1. Macro dashboard (point-in-time, month-end)."),
  img("10_alt_data_signals.png", 560, 0.579, { alt: "Alternative-data signals bar chart" }),
  cap("Figure A2. Alternative-data overlay: 21 unconventional indicators, z vs own 5y history, with the sectors each one maps to."),
  twoCol([img("11_region_comparison.png", 300, 0.727, { align: AlignmentType.LEFT }), cap("Figure A3. Same framework on Global / Europe sector sets.")],
    [img("02_regime_sector_heatmap.png", 360, 0.481, { align: AlignmentType.LEFT }), cap("Figure A4. Sector excess return by regime (2000-26).")], 4600),
  img("05_relative_strength_picks.png", 560, 0.497, { alt: "Relative strength of the six picks vs SPY" }),
  cap("Figure A5. Relative strength of the six picks vs SPY, last 12 months."),
  A("E. Agentic pipeline"),
  bullet("Weekly GitHub Actions cron → collect (yfinance, FRED, SSGA, TSA, Google Trends, RSS) → DuckDB/parquet with dated snapshots, so every run is reproducible."),
  bullet("Score → backtest → Claude news agent (structured output: policy stance, shocks with 1st/2nd-order effects, sector sentiment, conflicts with the model) → Excel workbook, charts and a markdown brief."),
  bullet("Headlines are treated as untrusted data in the agent prompt; the agent flags conflicts with the model and never changes positions on its own."),
  A("F. Question list for discussion"),
  ...[
    "Mandate: is the book beta-neutral or dollar-neutral? Are leverage and single-stock implementation allowed, or ETFs only?",
    "Horizon: is a 3-month hold with weekly review right, or should the overlay be monthly to cut noise?",
    "Should the weight on the macro layer scale with regime confidence (e.g. lower when the growth score is near zero, as now)?",
    "How do we treat the XLK concentration problem: cap-weighted vs equal-weight sector ETFs?",
    "Budget for point-in-time fundamentals and estimate revisions (Appendix B), the largest expected upgrade?",
    "Cross-country: build region-specific regimes (OECD CLI, HICP, ECB) before allocating outside the US? Hedge FX?",
    "Risk limits: max drawdown or stop-loss policy per leg; conviction-based sizing vs equal weight?",
    "How should the long-term themes (AI, ageing, energy transition) be weighted against tactical calls when they conflict (e.g. Utilities)?",
  ].map((q, i) => p([t(`${i + 1}. ${q}`, { size: 16 })], { after: 30 })),
];

const doc = new Document({
  creator: "Contrendian Project 1", title: "Sector Rotation & Long/Short Allocation: Proposal",
  styles: { default: { document: { run: { font: FONT, size: 18 } } } },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 260, hanging: 180 } } } }] }] },
  footnotes,
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 720, bottom: 720, left: 864, right: 864 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [t("Contrendian ◦ Project 1 · page ", { size: 14, color: INK2 }), new TextRun({ children: [PageNumber.CURRENT], size: 14, color: INK2, font: FONT })] })] }) },
    children: [...page1, ...page2, ...page3, ...appendix],
  }],
});
Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "output", "Contrendian_Project1_Proposal.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
