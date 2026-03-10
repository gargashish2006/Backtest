#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import subprocess
import argparse

def refresh_full_history(workers=20):
    print(f"--- Starting Full History Refresh (2017-2026) with {workers} workers ---", flush=True)
    
    project_root = Path(__file__).parent.parent
    instruments_csv = project_root / 'archive/source_data/dhan_instruments.csv'
    db_path = project_root / 'database'
    out_parquet = db_path / 'price_data_full.parquet'
    final_parquet = db_path / 'price_data.parquet'
    final_csv = db_path / 'price_data.csv'
    master_path = db_path / 'master_identifiers.parquet'
    
    # Clean env
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["PYTHONUNBUFFERED"] = "1"
    
    # 1. Download
    cmd = [
        "python3.12", "-m", "src.data.providers.dhan_download_daily",
        "--instruments", str(instruments_csv),
        "--start", "2017-01-01",
        "--end", "2026-02-09",
        "--out", str(out_parquet),
        "--chunk-days", "180",
        "--sleep", "0.05",
        "--workers", str(workers),
        "--retries", "3"
    ]
    
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Full download failed: {e}", flush=True)
        return

    if not out_parquet.exists():
        print("Output file not created. Aborting.")
        return

    # 2. Enrich with ISIN (Consistency check)
    print("--- Enriching with ISINs and Metadata ---", flush=True)
    import pandas as pd
    
    df_new = pd.read_parquet(out_parquet)
    df_master = pd.read_parquet(master_path)
    
    # Map symbols to ISINs
    nse_map = df_master.dropna(subset=['nse_symbol']).drop_duplicates('nse_symbol').set_index('nse_symbol')[['isin', 'company_name']].to_dict('index')
    df_master['bse_code_str'] = df_master['bse_code'].apply(lambda x: str(int(float(x))) if pd.notna(x) else None)
    bse_map = df_master.dropna(subset=['bse_code_str']).drop_duplicates('bse_code_str').set_index('bse_code_str')[['isin', 'company_name']].to_dict('index')
    
    def enrich_row(row):
        sym = str(row['symbol']).strip()
        is_nse = row['exchange_segment'] == 'NSE_EQ'
        if is_nse and sym in nse_map:
            m = nse_map[sym]
            return m['isin'], m['company_name'], 'NSE'
        if not is_nse and sym in bse_map:
            m = bse_map[sym]
            return m['isin'], m['company_name'], 'BSE'
        if sym in nse_map:
            m = nse_map[sym]
            return m['isin'], m['company_name'], 'NSE'
        if sym in bse_map:
            m = bse_map[sym]
            return m['isin'], m['company_name'], 'BSE'
        return None, None, 'NSE' if is_nse else 'BSE'

    enriched = df_new.apply(enrich_row, axis=1, result_type='expand')
    df_new['isin'] = enriched[0]
    df_new['company_name'] = enriched[1]
    df_new['exchange'] = enriched[2]
    
    initial_len = len(df_new)
    df_new = df_new.dropna(subset=['isin'])
    print(f"Mapped {initial_len} -> {len(df_new)} rows.", flush=True)

    # Format
    df_new = df_new[['isin', 'company_name', 'symbol', 'exchange', 'date', 'open', 'high', 'low', 'close', 'volume']]
    df_new['date'] = pd.to_datetime(df_new['date'])
    df_new = df_new.sort_values(['isin', 'date'])
    
    # 3. Replace Old Files
    print(f"--- Overwriting {final_parquet} ---", flush=True)
    df_new.to_parquet(final_parquet, index=False)
    
    print(f"--- Overwriting {final_csv} ---", flush=True)
    df_new.to_csv(final_csv, index=False)
    
    print("--- Full Refresh Complete ---", flush=True)

if __name__ == "__main__":
    refresh_full_history()
