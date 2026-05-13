"""
Compare 4 variants for Feb 2026 rebalance:
  CS15          — original (min_industry_stocks=1)
  CS15_limit    — min 3 stocks per industry
  CS15_delayed  — RSNP window anchored to shareholder quarter-end
  CS15_delayed_limit — delayed + min 3 stocks
"""
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).parent

from data.data_handler import DataHandler
from strategies.cs15_strategy import CS15Strategy
from strategies.cs15_delayed_strategy import CS15DelayedStrategy

RSNP_THRESHOLD = 0.40
MIN_STOCKS = 3

dh = DataHandler(REPO_ROOT / "database/price_data.parquet")
dh.load_data()
dh.load_benchmarks(REPO_ROOT / "benchmarks")

all_dates = dh.get_all_dates()
rebalance_date = max([d for d in all_dates if d <= pd.Timestamp("2026-02-15")])
print(f"Rebalance date: {rebalance_date.date()}\n")

variants = {
    'CS15':               CS15Strategy(dh, rsnp_benchmark='NIFTY 500', rsnp_threshold=RSNP_THRESHOLD, min_industry_stocks=1),
    'CS15_limit':         CS15Strategy(dh, rsnp_benchmark='NIFTY 500', rsnp_threshold=RSNP_THRESHOLD, min_industry_stocks=MIN_STOCKS),
    'CS15_delayed':       CS15DelayedStrategy(dh, rsnp_benchmark='NIFTY 500', rsnp_threshold=RSNP_THRESHOLD, min_industry_stocks=1),
    'CS15_delayed_limit': CS15DelayedStrategy(dh, rsnp_benchmark='NIFTY 500', rsnp_threshold=RSNP_THRESHOLD, min_industry_stocks=MIN_STOCKS),
}

results = {}
for name, strategy in variants.items():
    sel = strategy.calculate_selection(rebalance_date)
    results[name] = sel
    industries = list({dh.isin_to_industry.get(isin, 'Unknown') for isin in sel})
    print(f"{name}: {len(sel)} stocks across {len(industries)} industries")
    for isin, w in sel.items():
        cname = dh.isin_to_name.get(isin, isin)
        ind   = dh.isin_to_industry.get(isin, '?')
        print(f"  {cname:<45}  {ind:<35}  {w*100:.1f}%")
    print()

# Industry-level comparison table
all_industries = sorted(set(
    ind
    for sel in results.values()
    for isin in sel
    for ind in [dh.isin_to_industry.get(isin, '?')]
))

print("=" * 100)
print(f"{'Industry':<40} {'CS15':^12} {'CS15_limit':^12} {'CS15_delayed':^14} {'CS15_dlyd_lmt':^14}")
print("-" * 100)
for ind in all_industries:
    def ind_stocks(sel):
        return [dh.isin_to_name.get(i, i) for i in sel if dh.isin_to_industry.get(i) == ind]
    c1 = ind_stocks(results['CS15'])
    c2 = ind_stocks(results['CS15_limit'])
    c3 = ind_stocks(results['CS15_delayed'])
    c4 = ind_stocks(results['CS15_delayed_limit'])
    print(f"{ind:<40} {len(c1):^12} {len(c2):^12} {len(c3):^14} {len(c4):^14}")
    all_names = sorted(set(c1+c2+c3+c4))
    for nm in all_names:
        mark = lambda lst: 'Y' if nm in lst else '-'
        print(f"  {nm:<38} {mark(c1):^12} {mark(c2):^12} {mark(c3):^14} {mark(c4):^14}")
print("=" * 100)
