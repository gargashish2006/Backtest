import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

CLIENT_ID = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzczMDYxNzkwLCJpYXQiOjE3NzI5NzUzOTAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.zjZcwUxSRIEXWekym2ei2YG865Xie_Rw2IcJCxZ2qWGTzbAlyEnfxfjLjVhTOVMUH-20kHQ9flo9CoJ_n5OigA"

def fetch_extended():
    # 1. Load the comparison and classify stocks
    comparison_path = repo_root / "dhan_price_comparison.xlsx"
    df = pd.read_excel(comparison_path)
    jan22 = df[df['date'] == '2026-01-22'].copy()
    jan22['min_diff'] = jan22[['pct_diff_nse', 'pct_diff_bse']].min(axis=1)
    
    low_diff_isins = set(jan22[jan22['min_diff'] < 0.1]['isin'].unique())
    high_diff_isins = set(jan22[jan22['min_diff'] >= 0.1]['isin'].unique())
    
    print(f"Low-diff stocks (<0.1%): {len(low_diff_isins)}")
    print(f"High-diff stocks (>=0.1%): {len(high_diff_isins)}")
    
    # 2. Download Dhan master mapping
    mapping_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    print("Downloading Dhan master mapping...")
    try:
        df_map = pd.read_csv(mapping_url, low_memory=False)
        print(f"Downloaded mapping with {len(df_map)} records.")
    except Exception as e:
        print(f"Failed to download mapping: {e}")
        return

    stats_df = pd.read_csv(repo_root / "database/stock_statistics.csv")
    
    df_map_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    df_map_bse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'BSE') & (df_map['SEM_SEGMENT'] == 'E')]
    
    nse_lookup = df_map_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    bse_valid_codes = set(df_map_bse['SEM_SMST_SECURITY_ID'].astype(int).astype(str).tolist())
    
    # 3. Build fetch jobs
    # Each job: (isin, securityId, exchangeSegment, exchange_label, fromDate, toDate, chunk_id)
    fetch_jobs = []
    seen = set()
    
    for _, row in stats_df.iterrows():
        isin = row['isin']
        nse_sym = row.get('nse_symbol')
        bse_code = row.get('bse_code')
        
        if isin in low_diff_isins:
            # Fetch recent data, NSE only (preferred), fall back to BSE
            if pd.notna(nse_sym) and str(nse_sym) in nse_lookup:
                key = (isin, 'NSE', 'recent')
                if key not in seen:
                    seen.add(key)
                    fetch_jobs.append((isin, str(nse_lookup[str(nse_sym)]), 'NSE_EQ', 'NSE',
                                      '2026-01-23', '2026-03-06', 'recent'))
            elif pd.notna(bse_code):
                bse_str = str(int(bse_code))
                if bse_str in bse_valid_codes:
                    key = (isin, 'BSE', 'recent')
                    if key not in seen:
                        seen.add(key)
                        fetch_jobs.append((isin, bse_str, 'BSE_EQ', 'BSE',
                                          '2026-01-23', '2026-03-06', 'recent'))
                        
        elif isin in high_diff_isins:
            # Fetch full history, both exchanges, 2 chunks each
            # Chunk 1: 2016-02-01 to 2021-06-30
            # Chunk 2: 2021-07-01 to 2026-03-06
            if pd.notna(nse_sym) and str(nse_sym) in nse_lookup:
                sec_id = str(nse_lookup[str(nse_sym)])
                for chunk_id, (fd, td) in enumerate([('2016-02-01', '2021-06-30'), ('2021-07-01', '2026-03-06')]):
                    key = (isin, 'NSE', f'full_{chunk_id}')
                    if key not in seen:
                        seen.add(key)
                        fetch_jobs.append((isin, sec_id, 'NSE_EQ', 'NSE', fd, td, f'full_{chunk_id}'))
            
            if pd.notna(bse_code):
                bse_str = str(int(bse_code))
                if bse_str in bse_valid_codes:
                    for chunk_id, (fd, td) in enumerate([('2016-02-01', '2021-06-30'), ('2021-07-01', '2026-03-06')]):
                        key = (isin, 'BSE', f'full_{chunk_id}')
                        if key not in seen:
                            seen.add(key)
                            fetch_jobs.append((isin, bse_str, 'BSE_EQ', 'BSE', fd, td, f'full_{chunk_id}'))
    
    print(f"Total fetch jobs: {len(fetch_jobs)}")
    
    # 4. Resume support: check existing output
    out_path = repo_root / "dhan_extended_prices.parquet"
    temp_csv_path = repo_root / "temp_dhan_extended_prices.csv"
    
    existing_keys = set()
    if temp_csv_path.exists():
        try:
            df_ex = pd.read_csv(temp_csv_path)
            if not df_ex.empty and 'isin' in df_ex.columns and 'exchange' in df_ex.columns and 'chunk_id' in df_ex.columns:
                for _, r in df_ex.iterrows():
                    existing_keys.add((r['isin'], r['exchange'], r['chunk_id']))
                print(f"Loaded {len(existing_keys)} already processed (isin, exchange, chunk) combos.")
        except pd.errors.EmptyDataError:
            pass
    
    fetch_jobs = [j for j in fetch_jobs if (j[0], j[3], j[6]) not in existing_keys]
    print(f"Remaining jobs: {len(fetch_jobs)}")
    
    if len(fetch_jobs) == 0:
        print("All done! Converting to parquet...")
        _convert_to_parquet(temp_csv_path, out_path)
        return
    
    # 5. Setup API session
    url = "https://api.dhan.co/v2/charts/historical"
    headers = {
        "client-id": CLIENT_ID,
        "access-token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    csv_lock = threading.Lock()
    
    def fetch_one(isin, security_id, exchange_segment, exchange_label, from_date, to_date, chunk_id):
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": "EQUITY",
            "expiryCode": 0,
            "fromDate": from_date,
            "toDate": to_date
        }
        
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                resp_json = resp.json()
                closes = resp_json.get('close', [])
                opens = resp_json.get('open', [])
                highs = resp_json.get('high', [])
                lows = resp_json.get('low', [])
                volumes = resp_json.get('volume', [])
                timestamps = resp_json.get('timestamp', [])
                
                if not closes or not timestamps:
                    return [{'isin': isin, 'date': 'error', 'open': None, 'high': None,
                             'low': None, 'close': None, 'volume': None,
                             'exchange': exchange_label, 'chunk_id': chunk_id}]
                
                records = []
                for i in range(len(timestamps)):
                    dt = pd.to_datetime(timestamps[i], unit='s', utc=True).tz_convert('Asia/Kolkata')
                    records.append({
                        'isin': isin,
                        'date': dt.strftime('%Y-%m-%d'),
                        'open': opens[i] if i < len(opens) else None,
                        'high': highs[i] if i < len(highs) else None,
                        'low': lows[i] if i < len(lows) else None,
                        'close': closes[i] if i < len(closes) else None,
                        'volume': volumes[i] if i < len(volumes) else None,
                        'exchange': exchange_label,
                        'chunk_id': chunk_id
                    })
                return records
            else:
                return [{'isin': isin, 'date': 'error', 'open': None, 'high': None,
                         'low': None, 'close': None, 'volume': None,
                         'exchange': exchange_label, 'chunk_id': chunk_id}]
        except Exception as e:
            return [{'isin': isin, 'date': 'error', 'open': None, 'high': None,
                     'low': None, 'close': None, 'volume': None,
                     'exchange': exchange_label, 'chunk_id': chunk_id}]
    
    # 6. Run fetches
    print("Fetching extended data from Dhan incrementally...")
    count = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(fetch_one, *job): job for job in fetch_jobs}
        for future in as_completed(future_map):
            try:
                data = future.result()
                if data:
                    df_append = pd.DataFrame(data)
                    with csv_lock:
                        write_header = not temp_csv_path.exists() or temp_csv_path.stat().st_size == 0
                        df_append.to_csv(temp_csv_path, mode='a', header=write_header, index=False)
            except Exception as e:
                pass
            count += 1
            if count % 100 == 0:
                print(f"Processed {count}/{len(fetch_jobs)} jobs...")
    
    print("Fetching completed. Converting to parquet...")
    _convert_to_parquet(temp_csv_path, out_path)


def _convert_to_parquet(csv_path, parquet_path):
    """Convert the temp CSV to a clean parquet file."""
    df = pd.read_csv(csv_path)
    # Remove header rows and error rows
    df = df[df['isin'] != 'isin'].copy()
    df = df[df['date'] != 'error'].copy()
    
    # Convert types
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce').astype('Int64')
    df['date'] = pd.to_datetime(df['date'])
    
    # Drop chunk_id (only used for resume)
    df = df.drop(columns=['chunk_id'], errors='ignore')
    
    # Deduplicate
    df = df.drop_duplicates(subset=['isin', 'date', 'exchange'], keep='first')
    df = df.sort_values(['isin', 'exchange', 'date']).reset_index(drop=True)
    
    df.to_parquet(parquet_path, index=False)
    print(f"Saved {len(df)} records to {parquet_path}")
    print(f"Unique ISINs: {df['isin'].nunique()}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Exchange breakdown: {df['exchange'].value_counts().to_dict()}")


if __name__ == "__main__":
    fetch_extended()
