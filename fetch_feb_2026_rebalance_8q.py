import pandas as pd
from pathlib import Path
from data.data_handler import DataHandler

def generate_rebalance_data_8q():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    dh = DataHandler(repo_root / "database/price_data_cleaned.parquet")
    dh.load_data()
    
    # Rebalance Date: Mid-Feb 2026
    rebalance_date = pd.Timestamp("2026-02-15")
    
    # 1. Get Shareholder Trend (8Q Lookback)
    sh_trend = dh.get_shareholder_trend(rebalance_date, lookback_quarters=8)
    if sh_trend.empty:
        print("No shareholding data found for the requested period.")
        return
    
    # 2. Add Industry and Group mappings
    sh_trend['industry'] = sh_trend['isin'].map(dh.isin_to_industry)
    sh_trend['group'] = sh_trend['isin'].map(dh.isin_to_group)
    
    # 3. Calculate Industry level breadth
    ind_stats = sh_trend.groupby('industry')['decreased'].mean().reset_index()
    ind_stats.rename(columns={'decreased': 'industry_breadth'}, inplace=True)
    
    # 4. Calculate Group level breadth
    group_stats = sh_trend.groupby('group')['decreased'].mean().reset_index()
    group_stats.rename(columns={'decreased': 'group_breadth'}, inplace=True)
    
    # 5. Bring in Group mapping for Industries
    ind_to_group = sh_trend[['industry', 'group']].drop_duplicates()
    
    # 6. Merge everything
    final_df = pd.merge(ind_stats, ind_to_group, on='industry', how='left')
    final_df = pd.merge(final_df, group_stats, on='group', how='left')
    
    # Sort by Industry Breadth (Descending)
    final_df = final_df.sort_values('industry_breadth', ascending=False)
    
    # Print Top 20 Industries
    print("\n--- February 2026 Rebalance Signal: Top 20 Industries (8Q Lookback) ---")
    print(final_df.head(20).to_string(index=False))
    
    # Save to CSV and Excel
    csv_path = repo_root / "outputs/feb_2026_industry_signals_8q.csv"
    excel_path = repo_root / "outputs/feb_2026_industry_signals_8q.xlsx"
    final_df.to_csv(csv_path, index=False)
    
    # Format for Excel
    excel_df = final_df.copy()
    excel_df.columns = [col.replace('_', ' ').title() for col in excel_df.columns]
    excel_df.to_excel(excel_path, index=False, engine='openpyxl')
    
    print(f"\nSaved 8Q signal list to:")
    print(f"CSV: {csv_path}")
    print(f"Excel: {excel_path}")

if __name__ == "__main__":
    generate_rebalance_data_8q()
