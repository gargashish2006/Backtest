"""
Original Strategy Showdown: CS15 vs MCPS12.
Runs both strategies in their EXACT original configurations.

CS15 Original:
  - price_data.parquet (uncleaned)
  - start_date: 2017-05-15
  - FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125)
  - cash_yield_rate=0.05, cash_tax_rate=0.30

MCPS12 Original:
  - price_data_cleaned.parquet
  - start_date: 2017-05-15
  - FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125)
  - cash_yield_rate=0.05, cash_tax_rate=0.30
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import warnings
from data.data_handler import DataHandler
from engine.portfolio import Portfolio
from engine.accounting import FeeModel, TaxManager
from engine.sim_engine import SimEngine
from strategies.cs15_strategy import CS15Strategy
from strategies.mcps15_strategy import MCPS15Strategy
from utils.analytics import calculate_metrics

warnings.filterwarnings('ignore')

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

# --- CS15 uses original (uncleaned) price data ---
print("Loading CS15 data (price_data.parquet)...")
dh_cs15 = DataHandler(repo_root / "database/price_data.parquet")
dh_cs15.load_data()
dh_cs15.load_benchmarks(repo_root / "benchmarks")

# --- MCPS12 uses cleaned price data ---
print("Loading MCPS12 data (price_data_cleaned.parquet)...")
dh_mcps = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh_mcps.load_data()
dh_mcps.load_benchmarks(repo_root / "benchmarks")

start_date = "2017-05-15"
end_date   = "2026-02-05"

def get_rdates(dh):
    all_dates = dh.get_all_dates()
    rdates = sorted([
        max([dt for dt in all_dates if dt <= pd.Timestamp(year=y, month=m, day=15)])
        for y in range(2017, 2027) for m in [2, 5, 8, 11]
        if any(dt <= pd.Timestamp(year=y, month=m, day=15) for dt in all_dates)
    ])
    return [d for d in rdates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]

# --- Run CS15 ---
print("\nRunning CS15 (Original)...")
rdates_cs15 = get_rdates(dh_cs15)
strat_cs15 = CS15Strategy(dh_cs15, num_stocks=15)
strat_cs15.precompute_rsi(rdates_cs15)
port_cs15 = Portfolio(10_000_000)
eng_cs15 = SimEngine(dh_cs15, port_cs15, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125),
                     cash_yield_rate=0.05, cash_tax_rate=0.30)
eng_cs15.run(start_date, end_date, strat_cs15.calculate_selection, rdates_cs15, verbose=False)
nav_cs15 = pd.DataFrame(port_cs15.nav_history)
m_cs15 = calculate_metrics(nav_cs15)

# --- Run MCPS12 ---
print("Running MCPS12 (Original)...")
rdates_mcps = get_rdates(dh_mcps)
strat_mcps = MCPS15Strategy(dh_mcps, group_top_pct=0.50, num_stocks=12, max_per_industry=3)
strat_mcps.precompute_rsi(rdates_mcps)
port_mcps = Portfolio(10_000_000)
eng_mcps = SimEngine(dh_mcps, port_mcps, FeeModel(0.0015, 0.005), TaxManager(0.20, 0.125),
                     cash_yield_rate=0.05, cash_tax_rate=0.30)
eng_mcps.run(start_date, end_date, strat_mcps.calculate_selection, rdates_mcps, verbose=False)
nav_mcps = pd.DataFrame(port_mcps.nav_history)
m_mcps = calculate_metrics(nav_mcps)

# --- Print Results ---
print("\n" + "="*55)
print(f"{'Metric':<18} | {'CS15 (Original)':<15} | {'MCPS12 (Original)':<15}")
print("-" * 55)
for k in m_cs15.keys():
    print(f"{k:<18} | {m_cs15[k]:<15} | {m_mcps[k]:<15}")
print("="*55)

# --- Plot ---
fig, ax = plt.subplots(figsize=(15, 8))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

ax.plot(nav_cs15['date'], nav_cs15['nav'] / nav_cs15['nav'].iloc[0] * 100,
        color='#00d4ff', linewidth=3,
        label=f"CS15 (Original) | CAGR: {m_cs15['CAGR']} | MaxDD: {m_cs15['Max Drawdown']}")
ax.plot(nav_mcps['date'], nav_mcps['nav'] / nav_mcps['nav'].iloc[0] * 100,
        color='#ff9500', linewidth=3,
        label=f"MCPS12 (Original) | CAGR: {m_mcps['CAGR']} | MaxDD: {m_mcps['Max Drawdown']}")

ax.set_title("Original Strategy Showdown: CS15 vs MCPS12 (Net of Costs & Tax)", color='white', fontsize=18)
ax.set_ylabel("Normalized NAV", color='white')
ax.legend(facecolor='#1a1a2e', labelcolor='white')
ax.grid(True, color='#222222')
ax.tick_params(colors='white')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

out_path = repo_root / "original_strategies_comparison.png"
plt.tight_layout()
plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
print(f"\nSaved comparison plot to: {out_path}")
