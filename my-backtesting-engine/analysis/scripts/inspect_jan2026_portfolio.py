import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import os
import sys

# Add root directory to path to import strategy
sys.path.append(os.getcwd())
from strategies.industry_group.hierarchical_60_absolute_rs_monthly_exit import Hierarchical60AbsoluteRSMonthlyExit

def get_jan2026_portfolio():
    print(f"\n--- CALCULATING PORTFOLIO FOR JAN 2026 REBALANCE ---")
    print(f"Target Date: 2026-01-01")
    
    target_date = pd.to_datetime('2026-01-01')
    strat = Hierarchical60AbsoluteRSMonthlyExit()
    
    # Get qualifying industries
    ranked_inds = strat.get_qualifying_industries(target_date)
    
    if not ranked_inds:
        print("No qualifying industries found for Jan 2026.")
        # Let's see why - maybe relaxation of filters?
        return

    print(f"\nTop Qualifying Industries (by RS):")
    for i, ind in enumerate(ranked_inds[:10]):
        print(f"{i+1}. {ind}")

    # Calculate selection (Top 1000)
    stocks = strat.calculate_selection(target_date)
    
    if not stocks:
        print("No stocks selected from qualifying industries.")
        return

    # Get details
    industry_df = pd.read_parquet(strat.database_path / 'industry_info.parquet')
    price_df = pd.read_parquet(strat.database_path / 'price_data.parquet')
    
    # Get latest prices (as of Jan 1)
    p_slice = price_df[price_df['date'] <= target_date].sort_values('date').groupby('isin').last().reset_index()
    p_map = p_slice.set_index('isin')['close'].to_dict()
    
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
    
    print("\n--- JAN 2026 PREDICTED PORTFOLIO ---")
    print(df_res[['Company', 'Industry', 'Price', 'ISIN']].to_string(index=False))
    
    # Also show the industry mix
    print("\nINDUSTRY ALLOCATION:")
    print(df_res.groupby('Industry').size().sort_values(ascending=False))

if __name__ == "__main__":
    get_jan2026_portfolio()
