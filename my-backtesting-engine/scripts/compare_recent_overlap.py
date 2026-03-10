import pandas as pd
import subprocess
import os
from pathlib import Path
import sys

def compare_recent_overlap():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    db_path = project_root / 'database/price_data.parquet'
    instruments_csv = project_root / 'archive/source_data/dhan_instruments.csv'
    check_parquet = data_dir / 'jan_feb_2026_comparison.parquet'
    
    print("--- 1. Downloading Data (Jan 20, 2026 - Feb 9, 2026) ---")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [
        "python3.12", "-m", "src.data.providers.dhan_download_daily",
        "--instruments", str(instruments_csv),
        "--start", "2026-01-20",
        "--end", "2026-02-09",
        "--out", str(check_parquet),
        "--chunk-days", "30",
        "--workers", "1",
        "--sleep", "1.2",
        "--retries", "5"
    ]
    
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Download failed: {e}")
        return

    print("--- 2. Comparing with Existing Database ---")
    df_new = pd.read_parquet(check_parquet) # New Download
    df_db = pd.read_parquet(db_path)        # Existing DB (Historical)
    
    # Enrich df_new with ISINs
    master_path = project_root / 'database/master_identifiers.parquet'
    df_master = pd.read_parquet(master_path)
    
    nse_map = df_master.dropna(subset=['nse_symbol']).drop_duplicates('nse_symbol').set_index('nse_symbol')['isin'].to_dict()
    df_master['bse_code_str'] = df_master['bse_code'].apply(lambda x: str(int(float(x))) if pd.notna(x) else None)
    bse_map = df_master.dropna(subset=['bse_code_str']).drop_duplicates('bse_code_str').set_index('bse_code_str')['isin'].to_dict()

    def get_isin(row):
        sym = str(row['symbol']).strip()
        if row['exchange_segment'] == 'NSE_EQ': return nse_map.get(sym)
        return bse_map.get(sym)

    print("Mapping ISINs...")
    df_new['isin'] = df_new.apply(get_isin, axis=1)
    df_new = df_new.dropna(subset=['isin'])
    
    # Convert dates
    df_db['date'] = pd.to_datetime(df_db['date'])
    df_new['date'] = pd.to_datetime(df_new['date'])
    
    # Define Overlap Period for Comparison
    # We want to check dates where DB has "Old" data.
    # We know DB was updated with "New" data from Jan 28 onwards.
    # So "Old" data exists for dates < Jan 28.
    # Our download starts Jan 20.
    # So overlap is [Jan 20, Jan 27].
    
    start_overlap = pd.Timestamp("2026-01-20")
    end_overlap = pd.Timestamp("2026-01-27")
    
    print(f"Checking overlap window: {start_overlap.date()} to {end_overlap.date()}")
    
    # Filter both DFs to this window
    mask_db = (df_db['date'] >= start_overlap) & (df_db['date'] <= end_overlap)
    mask_new = (df_new['date'] >= start_overlap) & (df_new['date'] <= end_overlap)
    
    db_overlap = df_db[mask_db].set_index(['isin', 'date'])['close']
    new_overlap = df_new[mask_new].set_index(['isin', 'date'])['close']
    
    print(f"DB Records in window: {len(db_overlap)}")
    print(f"New Download Records in window: {len(new_overlap)}")
    
    # Align
    common_index = db_overlap.index.intersection(new_overlap.index)
    print(f"Common Data Points: {len(common_index)}")
    
    comparison = pd.DataFrame({
        'db_price': db_overlap.loc[common_index],
        'new_price': new_overlap.loc[common_index]
    })
    
    comparison['diff_pct'] = (comparison['db_price'] - comparison['new_price']).abs() / comparison['db_price']
    
    # Filter Mismatches > 0.1% (Ignore minor rounding)
    mismatches = comparison[comparison['diff_pct'] > 0.001].copy()
    
    affected_isins = mismatches.index.get_level_values('isin').unique()
    
    print(f"\nFound {len(affected_isins)} stocks with mismatching data in the overlap period.")
    
    if len(affected_isins) > 0:
        print("\nSample Mismatches (Top 10):")
        print(mismatches.sort_values('diff_pct', ascending=False).head(10))
        
        # Save list to file
        out_file = data_dir / "mismatched_stocks.csv"
        pd.Series(affected_isins).to_csv(out_file, index=False, header=['isin'])
        print(f"\nList of affected ISINs saved to: {out_file}")
        
    else:
        print("\n✅ No significant discrepancies found! The overlapping data matches.")

if __name__ == "__main__":
    compare_recent_overlap()
