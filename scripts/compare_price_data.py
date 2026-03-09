import pandas as pd
from pathlib import Path

def compare_prices():
    repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")
    local_path = repo_root / "temp_local_prices_jan23_27.csv"
    dhan_path = repo_root / "temp_dhan_prices_jan23_27.csv"
    out_path = repo_root / "dhan_price_comparison.xlsx"
    
    if not local_path.exists():
        print(f"Local prices file not found: {local_path}")
        return
    if not dhan_path.exists():
        print(f"Dhan prices file not found: {dhan_path}")
        return
        
    df_local = pd.read_csv(local_path)
    df_dhan = pd.read_csv(dhan_path)
    
    # Clean up: remove repeated headers and error rows
    df_dhan = df_dhan[df_dhan['isin'] != 'isin'].copy()
    df_dhan = df_dhan[df_dhan['date'] != 'error'].copy()
    df_dhan['dhan_close'] = pd.to_numeric(df_dhan['dhan_close'], errors='coerce')
    df_dhan = df_dhan.dropna(subset=['dhan_close'])
    
    # Deduplicate per (isin, date, exchange)
    df_dhan = df_dhan.drop_duplicates(subset=['isin', 'date', 'exchange'], keep='first')
    
    # Pivot: separate NSE and BSE prices into their own columns
    df_nse = df_dhan[df_dhan['exchange'] == 'NSE'][['isin', 'date', 'dhan_close']].rename(
        columns={'dhan_close': 'dhan_nse_close'})
    df_bse = df_dhan[df_dhan['exchange'] == 'BSE'][['isin', 'date', 'dhan_close']].rename(
        columns={'dhan_close': 'dhan_bse_close'})
    
    df_local = df_local.rename(columns={'close': 'local_close'})
    
    # Load company names (prefer NSE row for dual-listed)
    stats_df = pd.read_csv(repo_root / "database/stock_statistics.csv",
                           usecols=['isin', 'company_name', 'primary_exchange'])
    exchange_order = {'NSE': 0, 'BSE': 1}
    stats_df['_sort'] = stats_df['primary_exchange'].map(exchange_order).fillna(2)
    stats_df = stats_df.sort_values('_sort').drop_duplicates(subset=['isin'], keep='first')
    stats_df = stats_df.drop(columns=['_sort', 'primary_exchange'])
    
    # Start with local data, add NSE and BSE Dhan prices
    df_merged = df_local.copy()
    df_merged = pd.merge(df_merged, df_nse, on=['isin', 'date'], how='left')
    df_merged = pd.merge(df_merged, df_bse, on=['isin', 'date'], how='left')
    df_merged = pd.merge(df_merged, stats_df, on='isin', how='left')
    
    # Compute pct diff vs NSE and BSE
    df_merged['pct_diff_nse'] = ((df_merged['local_close'] - df_merged['dhan_nse_close']).abs() / df_merged['dhan_nse_close']) * 100
    df_merged['pct_diff_bse'] = ((df_merged['local_close'] - df_merged['dhan_bse_close']).abs() / df_merged['dhan_bse_close']) * 100
    
    # Use the best available pct_diff for sorting (prefer NSE, fall back to BSE)
    df_merged['pct_diff_best'] = df_merged['pct_diff_nse'].fillna(df_merged['pct_diff_bse'])
    
    # Sort by date then largest difference first
    df_merged = df_merged.sort_values(by=['date', 'pct_diff_best'], ascending=[True, False])
    
    # Reorder columns
    cols = ['company_name', 'isin', 'date', 'local_close', 
            'dhan_nse_close', 'pct_diff_nse',
            'dhan_bse_close', 'pct_diff_bse']
    df_merged = df_merged[[c for c in cols if c in df_merged.columns]]
    
    # Round pct_diff columns
    for c in ['pct_diff_nse', 'pct_diff_bse']:
        if c in df_merged.columns:
            df_merged[c] = df_merged[c].round(2)
    
    df_merged.to_excel(out_path, index=False)
    
    total = len(df_merged)
    nse_discr = (df_merged['pct_diff_nse'] > 1.0).sum() if 'pct_diff_nse' in df_merged.columns else 0
    bse_discr = (df_merged['pct_diff_bse'] > 1.0).sum() if 'pct_diff_bse' in df_merged.columns else 0
    print(f"Comparison complete. Exported {total} total records.")
    print(f"NSE discrepancies > 1%: {nse_discr}")
    print(f"BSE discrepancies > 1%: {bse_discr}")
    print(f"Exported to {out_path}")

if __name__ == "__main__":
    compare_prices()
