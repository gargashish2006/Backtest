"""
Diagnostic Script: Benchmark Comparison (Frictionless vs. Real-World)
Explains the discrepancy between 8.x% and 12.8% CAGR.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from utils.analytics import calculate_metrics

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()

# Quarterly rebalance dates
rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

def run_bench(name, fee_model, tax_manager, size=1000):
    print(f"Running Benchmark {name} (Size {size})...")
    p = Portfolio(10_000_000)
    e = SimEngine(dh, p, fee_model, tax_manager, cash_yield_rate=0, cash_tax_rate=0)
    def selection_logic(date):
        universe = dh.get_universe(date, size=size)
        isins = universe['isin'].tolist()
        return {isin: 1.0/len(isins) for isin in isins}
    e.run(start_date, end_date, selection_logic, rdates, verbose=False)
    metrics = calculate_metrics(pd.DataFrame(p.nav_history))
    return metrics['CAGR']

zero_fees = FeeModel(0, 0)
no_tax = TaxManager(0, 0)

cagr_1000 = run_bench("T1000 Frictionless", zero_fees, no_tax, size=1000)
cagr_500 = run_bench("T500 Frictionless", zero_fees, no_tax, size=500)
cagr_200 = run_bench("T200 Frictionless", zero_fees, no_tax, size=200)
cagr_100 = run_bench("T100 Frictionless", zero_fees, no_tax, size=100)

print("\n" + "=" * 60)
print(f"{'Benchmark (Frictionless)':<30} | {'CAGR':^20}")
print("-" * 60)
print(f"{'Top 1000':<30} | {cagr_1000:^20}")
print(f"{'Top 500':<30} | {cagr_500:^20}")
print(f"{'Top 200':<30} | {cagr_200:^20}")
print(f"{'Top 100':<30} | {cagr_100:^20}")
print("=" * 60)
