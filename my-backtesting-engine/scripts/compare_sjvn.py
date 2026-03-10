import pandas as pd
import numpy as np

def compare_sjvn():
    print("--- Loading Data ---")
    # Load old (mixed) data
    df_old_full = pd.read_parquet('database/price_data.parquet')
    df_old = df_old_full[df_old_full['isin'] == 'INE002L01015'].copy()
    df_old['date'] = pd.to_datetime(df_old['date'])
    df_old = df_old.sort_values('date').set_index('date')
    print(f"Old Data Rows: {len(df_old)}")
    
    # Load new (clean) data
    df_new = pd.read_parquet('data/sjvn_2025.parquet')
    df_new['date'] = pd.to_datetime(df_new['date'])
    df_new = df_new.sort_values('date').set_index('date')
    print(f"New Data Rows: {len(df_new)}")
    
    # Merge
    merged = df_old[['close']].join(df_new[['close']], lsuffix='_old', rsuffix='_new', how='inner')
    merged['ratio'] = merged['close_old'] / merged['close_new']
    merged['diff_pct'] = ((merged['close_old'] - merged['close_new']) / merged['close_new']).abs()
    
    # Identify discrepancies > 1%
    discrepancies = merged[merged['diff_pct'] > 0.01].copy()
    
    if discrepancies.empty:
        print("No significant discrepancies found.")
        return

    print(f"\nFound {len(discrepancies)} days with discrepancies > 1%.")
    
    # Analyze Ratio Stability
    # Group consecutive dates with similar ratios
    merged['ratio_rounded'] = merged['ratio'].round(4)
    # Filter for significant deviation from 1.0
    affected = merged[abs(merged['ratio'] - 1.0) > 0.01].copy()
    
    if affected.empty:
         print("Differences are minor noise.")
    else:
         print("\n--- Adjustment Factor Analysis ---")
         print(affected['ratio_rounded'].value_counts().head(5))
         
         print("\n--- Timeline Analysis ---")
         # Find where the ratio changes
         affected['ratio_change'] = affected['ratio_rounded'].diff().fillna(0)
         changes = affected[affected['ratio_change'] != 0]
         if len(changes) < 20:
             print(changes[['close_old', 'close_new', 'ratio']])
         else:
             print("Too many changes, showing first and last 5:")
             print(changes[['close_old', 'close_new', 'ratio']].head(5))
             print(changes[['close_old', 'close_new', 'ratio']].tail(5))
             
    # Specific check around recent dates
    print("\n--- Recent Data (Jan-Feb 2026) ---")
    print(merged['2026-01-15':].head(20))

if __name__ == "__main__":
    compare_sjvn()
