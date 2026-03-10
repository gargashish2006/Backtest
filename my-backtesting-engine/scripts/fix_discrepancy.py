
import pandas as pd
import subprocess
import os
from pathlib import Path
import sys

def fix_discrepancies():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    db_path = project_root / 'database/price_data.parquet'
    instruments_csv = project_root / 'archive/source_data/dhan_instruments.csv'
    check_parquet = data_dir / 'jan2026_check.parquet'
    
    print("--- 1. Downloading Jan 2026 Data for Comparison ---")
    # Download Jan 1, 2026 to Feb 9, 2026 for ALL instruments
    # This serves as the 'New Data' baseline
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [
        "python3.12", "-m", "src.data.providers.dhan_download_daily",
        "--instruments", str(instruments_csv),
        "--start", "2026-01-01",
        "--end", "2026-02-09",
        "--out", str(check_parquet),
        "--chunk-days", "60",
        "--workers", "20",
        "--sleep", "0.05"
    ]
    
    try:
        if not check_parquet.exists(): # Only run if not already caught from previous partials
            subprocess.run(cmd, env=env, check=True)
        else:
            print("Using existing jan2026_check.parquet")
    except subprocess.CalledProcessError as e:
        print(f"Download failed: {e}")
        return

    print("--- 2. Identifying Affected Stocks ---")
    df_new = pd.read_parquet(check_parquet)
    df_db = pd.read_parquet(db_path) # Contains mixed history (Old < Jan28, New >= Jan28)
    
    # Enrich df_new with ISINs to match DB keys
    # (Borrow enrichment logic or just map based on symbol if unique enough, 
    #  but safest to use the existing ISINs in DB if symbols align)
    
    # Actually, we can just use Symbol for matching if we are careful, 
    # but DB is keyed by ISIN.
    # Let's map df_new symbols to ISINs using the master file again to be safe.
    master_path = project_root / 'database/master_identifiers.parquet'
    df_master = pd.read_parquet(master_path)
    
    # Fast map
    nse_map = df_master.dropna(subset=['nse_symbol']).drop_duplicates('nse_symbol').set_index('nse_symbol')['isin'].to_dict()
    df_master['bse_code_str'] = df_master['bse_code'].apply(lambda x: str(int(float(x))) if pd.notna(x) else None)
    bse_map = df_master.dropna(subset=['bse_code_str']).drop_duplicates('bse_code_str').set_index('bse_code_str')['isin'].to_dict()

    def get_isin(row):
        sym = str(row['symbol']).strip()
        if row['exchange_segment'] == 'NSE_EQ': return nse_map.get(sym)
        return bse_map.get(sym)

    df_new['isin'] = df_new.apply(get_isin, axis=1)
    df_new = df_new.dropna(subset=['isin'])
    
    # Filter for comparison date: Jan 27, 2026 (The day BEFORE the overlap/switch)
    # On this date, DB has OLD price, df_new has NEW price.
    compare_date = pd.Timestamp("2026-01-27")
    
    df_db['date'] = pd.to_datetime(df_db['date'])
    df_new['date'] = pd.to_datetime(df_new['date'])
    
    old_prices = df_db[df_db['date'] == compare_date].set_index('isin')['close']
    new_prices = df_new[df_new['date'] == compare_date].set_index('isin')['close']
    
    # Align
    common = old_prices.index.intersection(new_prices.index)
    comparison = pd.DataFrame({'old': old_prices[common], 'new': new_prices[common]})
    
    # Calculate Ratio
    comparison['ratio'] = comparison['new'] / comparison['old']
    comparison['diff'] = (comparison['new'] - comparison['old']).abs() / comparison['old']
    
    # Detect Discrepancies > 1%
    affected = comparison[comparison['diff'] > 0.01].copy()
    print(f"Found {len(affected)} stocks with discrepancies on {compare_date.date()}")
    
    if len(affected) == 0:
        print("No adjustments needed.")
        return

    print("Sample Discrepancies:")
    print(affected.head(5))

    print("--- 3. Applying Adjustments to History ---")
    # Factor to apply to OLD history to make it match NEW history:
    # We want Old * Factor = New
    # So Factor = New / Old (which is 'ratio')
    
    # We apply this factor to all dates < Jan 28, 2026 for the affected ISINs
    cutoff_date = pd.Timestamp("2026-01-28")
    
    # Create map
    factor_map = affected['ratio'].to_dict()
    
    # Vectorized update
    # 1. Map factor to full DB
    df_db['factor'] = df_db['isin'].map(factor_map).fillna(1.0)
    
    # 2. Identify rows to adjust
    mask = (df_db['date'] < cutoff_date) & (df_db['factor'] != 1.0)
    
    print(f"Adjusting {mask.sum()} rows...")
    
    cols = ['open', 'high', 'low', 'close']
    for c in cols:
        df_db.loc[mask, c] = df_db.loc[mask, c] * df_db.loc[mask, 'factor']
        
    df_db.drop(columns=['factor'], inplace=True)
    
    print("--- 4. Saving Repaired Database ---")
    df_db.to_parquet(db_path, index=False)
    df_db.to_csv(project_root / 'database/price_data.csv', index=False)
    
    print("Repair Complete.")

if __name__ == "__main__":
    fix_discrepancies()
