"""
Diagnostic: Why do MCPS15 thresholds produce identical results?
Check how many industries pass each threshold at each rebalance date.
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPS15Strategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data.parquet")
dh.load_data()
dh.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()

rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

s = MCPS15Strategy(dh)
s.precompute_rsi(rdates)

print(f"\n{'Date':<14} | {'Total Inds':>10} | {'>=0%':>8} | {'>=30%':>8} | {'>=50%':>8} | {'>=70%':>8} | {'Dist of MCPS%'}")
print("-" * 100)

all_pcts = []
for date in rdates:
    signal_date = date - pd.Timedelta(days=7)
    actual_signal = max([d for d in all_dates if d <= signal_date])
    ind_ranked = s._get_mcps_ranking(actual_signal)
    if ind_ranked.empty:
        print(f"{str(date.date()):<14} | {'NO DATA':>10}")
        continue

    pcts = ind_ranked['mcps_positive_pct'].values
    all_pcts.extend(pcts)
    n_total = len(pcts)
    n_0   = (pcts >= 0.0).sum()
    n_30  = (pcts >= 0.3).sum()
    n_50  = (pcts >= 0.5).sum()
    n_70  = (pcts >= 0.7).sum()

    # Distribution buckets
    dist = f"0-30%:{(pcts<0.3).sum()} | 30-50%:{((pcts>=0.3)&(pcts<0.5)).sum()} | 50-70%:{((pcts>=0.5)&(pcts<0.7)).sum()} | 70-100%:{(pcts>=0.7).sum()}"
    print(f"{str(date.date()):<14} | {n_total:>10} | {n_0:>8} | {n_30:>8} | {n_50:>8} | {n_70:>8} | {dist}")

# Overall distribution
all_pcts_s = pd.Series(all_pcts)
print(f"\n{'='*60}")
print(f"Overall MCPS positive % distribution across all rebalances:")
print(f"  Mean:   {all_pcts_s.mean()*100:.1f}%")
print(f"  Median: {all_pcts_s.median()*100:.1f}%")
print(f"  Std:    {all_pcts_s.std()*100:.1f}%")
print(f"  Min:    {all_pcts_s.min()*100:.1f}%")
print(f"  Max:    {all_pcts_s.max()*100:.1f}%")
print(f"\n  % of industries with MCPS >= 0%:  {(all_pcts_s>=0.0).mean()*100:.1f}%")
print(f"  % of industries with MCPS >= 30%: {(all_pcts_s>=0.3).mean()*100:.1f}%")
print(f"  % of industries with MCPS >= 50%: {(all_pcts_s>=0.5).mean()*100:.1f}%")
print(f"  % of industries with MCPS >= 70%: {(all_pcts_s>=0.7).mean()*100:.1f}%")
