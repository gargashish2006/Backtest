import pandas as pd
from pathlib import Path
import shutil

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
db_path = repo_root / "database/price_data.parquet"
backup_path = repo_root / "database/price_data_backup_pre_dhan.parquet"
comparison_path = repo_root / "dhan_price_comparison.xlsx"
extended_path = repo_root / "dhan_extended_prices.parquet"

def integrate_dhan_prices():
    print("Loading data...")
    df_local = pd.read_parquet(db_path)
    df_ext = pd.read_parquet(extended_path)
    df_comp = pd.read_excel(comparison_path)
    
    # Classify ISINs based on Jan 22 diff
    jan22 = df_comp[df_comp['date'] == '2026-01-22'].copy()
    jan22['min_diff'] = jan22[['pct_diff_nse', 'pct_diff_bse']].min(axis=1)
    
    high_diff_isins = set(jan22[jan22['min_diff'] >= 0.1]['isin'].unique())
    low_diff_isins = set(jan22[jan22['min_diff'] < 0.1]['isin'].unique())
    
    print(f"ISINs to replace (high diff): {len(high_diff_isins)}")
    print(f"ISINs to extend (low diff): {len(low_diff_isins)}")
    
    # Backup original DB
    if not backup_path.exists():
        print(f"Creating backup at {backup_path}")
        shutil.copy2(db_path, backup_path)
    
    # Process extended data to prefer NSE
    # Sort by isin, date, and exchange (NSE before BSE)
    df_ext['exch_rank'] = df_ext['exchange'].map({'NSE': 0, 'BSE': 1}).fillna(2)
    df_ext = df_ext.sort_values(['isin', 'date', 'exch_rank'])
    df_ext_clean = df_ext.drop_duplicates(subset=['isin', 'date'], keep='first').copy()
    
    results = []
    
    # 1. Keep stocks that are NOT in our Dhan fetch list at all
    processed_isins = high_diff_isins.union(low_diff_isins)
    df_other = df_local[~df_local['isin'].isin(processed_isins)]
    results.append(df_other)
    
    # 2. Handle Low-diff stocks: Extend history forward
    print("Processing low-diff stocks (extension)...")
    df_low_local = df_local[df_local['isin'].isin(low_diff_isins)]
    df_low_ext = df_ext_clean[df_ext_clean['isin'].isin(low_diff_isins)]
    
    # Filter dhan data for dates after local max date (to avoid overlapping duplicates if any)
    # Actually, simpler: Drop local dates that overlap with Dhan dates, then concat
    # But user wanted Jan 23 onwards from Dhan.
    max_local_dates = df_low_local.groupby('isin')['date'].max()
    
    # Append the new data
    results.append(df_low_local)
    # Only take records from Dhan that are strictly after the max date in local for that ISIN
    to_add = []
    for isin in low_diff_isins:
        if isin in max_local_dates:
            last_date = max_local_dates[isin]
            new_data = df_low_ext[(df_low_ext['isin'] == isin) & (df_low_ext['date'] > last_date)]
            if not new_data.empty:
                to_add.append(new_data[['date', 'isin', 'close']])
    if to_add:
        results.append(pd.concat(to_add))
        
    # 3. Handle High-diff stocks: Full replacement
    print("Processing high-diff stocks (replacement)...")
    df_high_ext = df_ext_clean[df_ext_clean['isin'].isin(high_diff_isins)]
    results.append(df_high_ext[['date', 'isin', 'close']])
    
    # Combine everything
    print("Combining datasets...")
    df_final = pd.concat(results, ignore_index=True)
    
    # Final cleanup
    df_final = df_final.dropna(subset=['close'])
    df_final = df_final.drop_duplicates(subset=['isin', 'date'], keep='last')
    df_final = df_final.sort_values(['isin', 'date']).reset_index(drop=True)
    
    print(f"Final record count: {len(df_final)} (Original: {len(df_local)})")
    
    # Save
    df_final.to_parquet(db_path, index=False)
    print(f"Database updated successfully at {db_path}")

if __name__ == "__main__":
    integrate_dhan_prices()
