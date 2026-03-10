import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_rebalance_data():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # Rebalance Date: Mid-Feb 2026
    rebalance_date = pd.Timestamp("2026-02-15")
    
    # 1. Get Shareholder Trend (12Q Lookback)
    sh_trend = dh.get_shareholder_trend(rebalance_date, lookback_quarters=12)
    if sh_trend.empty:
        print("No shareholding data found for the requested period.")
        return
    
    # 2. Add Industry and Group mappings
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    
    # 3. Calculate Industry level breadth
    # Mean of 'decreased' flag = percentage of stocks cleaning
    ind_stats = sh_trend.groupby('industry')['decreased'].mean().reset_index()
    ind_stats.rename(columns={'decreased': 'industry_breadth'}, inplace=True)
    
    # 4. Calculate Group level breadth
    group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
    group_stats.rename(columns={'decreased': 'group_breadth'}, inplace=True)
    
    # 5. Bring in Group mapping for Industries
    # An industry always belongs to one group in this schema
    ind_to_group = sh_trend[['industry', 'group']].drop_duplicates()
    
    # 6. Merge everything
    final_df = pd.merge(ind_stats, ind_to_group, on='industry', how='left')
    final_df = pd.merge(final_df, group_stats, on='group', how='left')
    
    # Sort by Industry Breadth (Descending)
    final_df = final_df.sort_values('industry_breadth', ascending=False)
    
    # Display Top 15 Industries
    print("\n--- February 2026 Rebalance Signal: Top 15 Industries ---")
    print(final_df.head(20).to_string(index=False))
    
    # Save to CSV for reference
    final_df.to_csv(repo_root / "feb_2026_industry_signals.csv", index=False)
    print(f"\nSaved full signal list to: {repo_root}/feb_2026_industry_signals.csv")

if __name__ == "__main__":
    generate_rebalance_data()
