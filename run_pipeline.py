"""End-to-end weekly run:  collect -> score -> backtest -> LLM news scan -> report.

    python run_pipeline.py            # full run (re-downloads data)
    python run_pipeline.py --no-fetch # reuse data/ snapshots
"""
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).parent / "src")]

import warnings
warnings.filterwarnings("ignore")

import agent
import alt_data
import collect
import international
import model as M
import report as R
import site_build


def main():
    if "--no-fetch" not in sys.argv:
        collect.collect_all()
        alt_data.collect_alt()
        international.collect_international()
    sig = M.build_signals()
    tab, _ = M.live_scores(sig)
    news = agent.run_news_scan(tab)
    out = R.build_all(sig, news)
    t = out["table"]
    print("\nLONG :", ", ".join(t.index[t.Call == "LONG"]))
    print("SHORT:", ", ".join(t.index[t.Call == "SHORT"]))
    print(f"Excel: {out['excel']}\nBrief: {out['brief']}")
    print(f"Site:  {site_build.build_site(sig)}")


if __name__ == "__main__":
    main()
