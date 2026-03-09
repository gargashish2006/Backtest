"""
Cross-Check: Raw Data Benchmark Calculation
To see if the 8-9% CAGR comes from the raw (uncleaned) dataset.
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
dh = DataHandler(repo_root / "database/price_data.parquet")
dh.load_data()

start_date = "2017-05-15"
end_date   = "2026-02-05"
all_dates  = dh.get_all_dates()

rdates = sorted([
    max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
    for y in range(2017, 2027) for m in [2, 5, 8, 11]
    if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
])
rdates = [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

p = Portfolio(10_000_000)
e = SimEngine(dh, p, FeeModel(0,0), TaxManager(0,0), cash_yield_rate=0, cash_tax_rate=0)
def selection_logic(date):
    universe = dh.get_universe(date, size=1000)
    isins = universe['isin'].tolist()
    return {isin: 1.0/len(isins) for isin in isins}

e.run(start_date, end_date, selection_logic, rdates, verbose=False)
stats = calculate_metrics(pd.DataFrame(p.nav_history))

print(f"\nRAW DATA Top 1000 Benchmark Results:")
print(f"CAGR: {stats['CAGR']}")
print(f"Max DD: {stats['Max Drawdown']}")
print(f"Abs Return: {(p.nav_history[-1]['nav']/10_000_000 - 1)*100:.2f}%")
