#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import subprocess
import os
import sys

def update_price_data(start_date, end_date, workers=5):
    print(f"Orchestrator started with {workers} workers...", flush=True)
    project_root = Path(__file__).parent.parent
    db_path = project_root / 'database'
    price_parquet = db_path / 'price_data.parquet'
    price_csv = db_path / 'price_data.csv'
    master_path = db_path / 'master_identifiers.parquet'
    instruments_csv = project_root / 'archive/source_data/dhan_instruments.csv'
    if not instruments_csv.exists():
        print(f"Instruments file not found at {instruments_csv}")
        return
    
    # Check instruments count
    import csv
    with open(instruments_csv, 'r') as f:
        reader = csv.DictReader(f)
        inst_count = sum(1 for row in reader)
    print(f"Loaded {inst_count} instruments from {instruments_csv.name}", flush=True)

    temp_new = project_root / 'data/temp_new_prices.parquet'
    
    # 1. Download new data using the existing module
    print(f"--- Downloading new data from {start_date} to {end_date} ---", flush=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [
        "python3.12", "-m", "src.data.providers.dhan_download_daily",
        "--instruments", str(instruments_csv),
        "--start", start_date,
        "--end", end_date,
        "--out", str(temp_new),
        "--chunk-days", "15",
        "--sleep", "0.05",
        "--workers", str(workers)
    ]
    
    try:
        # Run with explicit env and without capturing output so we see it
        result = subprocess.run(cmd, env=env, check=True)
        print(f"Download process finished with return code {result.returncode}", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"Download failed with return code {e.returncode}", flush=True)
        print(f"Command: {' '.join(cmd)}", flush=True)
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}", flush=True)
        return

    if not temp_new.exists():
        print("No new data was downloaded.")
        return

    # 2. Load new data and enrich with ISIN/Company Name
    print("--- Enriching new data with ISINs and Company Names ---", flush=True)
    df_new = pd.read_parquet(temp_new)
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

    print("  Mapping rows to ISINs...", flush=True)
    enriched = df_new.apply(enrich_row, axis=1, result_type='expand')
    df_new['isin'] = enriched[0]
    df_new['company_name'] = enriched[1]
    df_new['exchange'] = enriched[2]
    
    df_new = df_new.dropna(subset=['isin'])
    df_new['date'] = pd.to_datetime(df_new['date'])
    df_new = df_new[['isin', 'company_name', 'symbol', 'exchange', 'date', 'open', 'high', 'low', 'close', 'volume']]

    # 3. Corporate Action Verification
    print("--- Verifying Corporate Actions at overlap date ---", flush=True)
    df_old = pd.read_parquet(price_parquet)
    df_old['date'] = pd.to_datetime(df_old['date'])
    overlap_date = pd.to_datetime(start_date)
    
    common_isins = set(df_old['isin']).intersection(set(df_new['isin']))
    old_overlap = df_old[df_old['date'] == overlap_date].set_index('isin')['close']
    new_overlap = df_new[df_new['date'] == overlap_date].set_index('isin')['close']
    
    common_at_date = old_overlap.index.intersection(new_overlap.index)
    if len(common_at_date) > 0:
        diff = (new_overlap[common_at_date] - old_overlap[common_at_date]).abs() / old_overlap[common_at_date]
        flagged = diff[diff > 0.01] # > 1% difference
        if not flagged.empty:
            print(f"WARNING: Potential corporate actions or data adjustments detected for {len(flagged)} stocks:", flush=True)
            for isin, p_diff in flagged.head(10).items():
                print(f"  ISIN {isin}: New Price={new_overlap[isin]:.2f}, Old Price={old_overlap[isin]:.2f} (Diff={p_diff:.2%})", flush=True)
            if len(flagged) > 10:
                print(f"  ... and {len(flagged)-10} more.", flush=True)
        else:
            print(f"  Price verification passed for {len(common_at_date)} stocks at overlap date {start_date}.", flush=True)
    else:
        print(f"  No common data at overlap date {start_date} to verify.", flush=True)

    # 4. Merge
    print(f"--- Merging with {price_parquet.name} ---", flush=True)
    df_combined = pd.concat([df_old, df_new], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=['isin', 'date'], keep='last')
    df_combined = df_combined.sort_values(['isin', 'date'])
    
    df_combined.to_parquet(price_parquet, index=False)
    print(f"  Parquet updated: {len(df_combined):,} rows.", flush=True)

    print(f"--- Updating {price_csv.name} ---", flush=True)
    df_combined.to_csv(price_csv, index=False)
    print(f"  CSV updated.", flush=True)

    if temp_new.exists():
        temp_new.unlink()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers")
    args = parser.parse_args()
    update_price_data(args.start, args.end, args.workers)
