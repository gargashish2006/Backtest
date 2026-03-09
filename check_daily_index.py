"""
Cross-Check: Daily Rebalanced Top 1000 Index Calculation
Matches the stored benchmark methodology.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from data.data_handler import DataHandler

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
dh.load_data()

# Start on 2017-05-15
start_date = pd.Timestamp("2017-05-15")
end_date = pd.Timestamp("2026-02-05")
all_dates = sorted([d for d in dh.get_all_dates() if start_date <= d <= end_date])

price_pivot = dh.price_df.pivot(index='date', columns='isin', values='close')

def calculate_daily_index():
    index_value = 1000.0
    index_history = []
    
    for i in range(len(all_dates)-1):
        curr_date = all_dates[i]
        next_date = all_dates[i+1]
        
        # Get universe on current date
        universe = dh.get_universe(curr_date, size=1000)
        isins = universe['isin'].tolist()
        
        # Calculate daily returns for these 1000 stocks
        valid_isins = [isin for isin in isins if isin in price_pivot.columns]
        p_curr = price_pivot.loc[curr_date, valid_isins]
        p_next = price_pivot.loc[next_date, valid_isins]
        
        daily_ret = (p_next / p_curr).mean() # Equal weight daily
        index_value *= daily_ret
        index_history.append({'date': next_date, 'index_value': index_value})
        
    return pd.DataFrame(index_history)

df_daily = calculate_daily_index()
start_val = 1000.0
end_val = df_daily.iloc[-1]['index_value']
abs_ret = (end_val / start_val - 1) * 100
cagr = (end_val / start_val) ** (1 / (len(df_daily)/252)) - 1

print(f"\nDaily Rebalanced Top 1000 Index Results:")
print(f"Start: {all_dates[0]} | Val: {start_val}")
print(f"End:   {all_dates[-1]} | Val: {end_val:.2f}")
print(f"Abs Return: {abs_ret:.2f}%")
print(f"CAGR: {cagr*100:.2f}%")

# Stored benchmark reference (from my previous analysis)
# 1390.73 -> 3006.47 => 116.18% Abs Return => ~9.3% CAGR
print("\nStored Benchmark Comparison:")
print("Abs Return: ~116.18%")
print("CAGR: ~9.3%")
