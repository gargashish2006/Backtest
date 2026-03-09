"""
Diagnostic Script: RSI Cache Inspection
"""
import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler
from strategies.mcps15_strategy import MCPSStrategy

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

s = MCPSStrategy(dh, universe_size=500)
rebalance_date = pd.Timestamp("2026-02-15")
s.precompute_rsi([rebalance_date])

print(f"RSI Cache Shape: {s.rsi_cache.shape}")
print(f"RSI Cache Index (Last 5): {s.rsi_cache.index[-5:]}")

isins = {
    'HDFC Bank': 'INE040A01034',
    'ICICI Bank': 'INE090A01021',
    'Axis Bank': 'INE238A01034'
}

for name, isin in isins.items():
    exists = isin in s.rsi_cache.columns
    val = s.rsi_cache.loc[rebalance_date, isin] if (exists and rebalance_date in s.rsi_cache.index) else "N/A (Not in Index/Col)"
    print(f"{name} ({isin}): Exists in Cols={exists} | Val @ {rebalance_date}={val}")
    if exists:
        # Check last valid value
        last_val = s.rsi_cache[isin].dropna().tail(1).values
        print(f"   Last non-NaN Val: {last_val}")

print(f"\nIs Feb 15 in Cache Index? {rebalance_date in s.rsi_cache.index}")
# If not, how does the strategy retrieve it?
# In strategy: rsi_val = self.rsi_cache.loc[date, isin]
