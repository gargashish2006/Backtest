import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Import the strategy class logic (or a simplified version for inspection)
import os
import sys
sys.path.append(os.getcwd())
from strategies.industry_group.hierarchical_60_absolute_rs_monthly_exit import Hierarchical60AbsoluteRSMonthlyExit

def inspect_portfolio(target_date_str):
    print(f"\n--- INSPECTING PORTFOLIO AT {target_date_str} ---")
    target_date = pd.to_datetime(target_date_str)
    
    strat = Hierarchical60AbsoluteRSMonthlyExit()
    
    # We need to simulate the selection at that date.
    # Note: The strategy keeps state (permanently_excluded). 
    # For a snapshot, we'll assume nothing was excluded yet or we just look at the selection logic.
    
    # Simplified selection logic for inspection
    portfolio = {} # Empty portfolio for a fresh rebalance view
    stocks = strat.calculate_selection(target_date, portfolio)
    
    if not stocks:
        print("No stocks selected at this date.")
        return

    # Get details for these stocks
    industry_df = pd.read_parquet(strat.database_path / 'industry_info.parquet')
    price_df = pd.read_parquet(strat.database_path / 'price_data.parquet')
    
    # Get prices at that date
    p_slice = price_df[price_df['date'] == target_date]
    p_map = p_slice.set_index('isin')['close'].to_dict()
    
    # Get names and industries
    results = []
    for isin in stocks:
        ind_info = industry_df[industry_df['isin'] == isin].iloc[0]
        results.append({
            'ISIN': isin,
            'Company': ind_info['company_name'],
            'Industry': ind_info['industry'],
            'Price': p_map.get(isin, 0)
        })
    
    df_res = pd.DataFrame(results)
    
    # Show summary by industry
    print("\nINDUSTRY SUMMARY:")
    print(df_res.groupby('Industry').size().sort_values(ascending=False))
    
    print("\nFULL STOCK LIST:")
    print(df_res[['Company', 'Industry', 'Price', 'ISIN']].to_string(index=False))

if __name__ == "__main__":
    dates = ['2020-02-01', '2020-05-01', '2021-02-01']
    for d in dates:
        inspect_portfolio(d)
