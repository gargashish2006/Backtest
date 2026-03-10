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

repo_root = Path("/Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/precision-backtest-engine")

CLIENT_ID = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzczMDYxNzkwLCJpYXQiOjE3NzI5NzUzOTAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.zjZcwUxSRIEXWekym2ei2YG865Xie_Rw2IcJCxZ2qWGTzbAlyEnfxfjLjVhTOVMUH-20kHQ9flo9CoJ_n5OigA"

def fetch_dhan_prices():
    mapping_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    print("Downloading Dhan master mapping...")
    try:
        df_map = pd.read_csv(mapping_url, low_memory=False)
        print(f"Downloaded mapping with {len(df_map)} records.")
    except Exception as e:
        print(f"Failed to download mapping: {e}")
        return

    local_df = pd.read_csv(repo_root / "temp_local_prices_jan23_27.csv")
    isins = set(local_df['isin'].unique())
    
    stats_df = pd.read_csv(repo_root / "database/stock_statistics.csv")
    
    if 'SEM_EXM_EXCH_ID' not in df_map.columns:
        print(f"Unexpected columns: {df_map.columns}")
        return
        
    df_map_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    df_map_bse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'BSE') & (df_map['SEM_SEGMENT'] == 'E')]
    
    nse_lookup = df_map_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    bse_valid_codes = set(df_map_bse['SEM_SMST_SECURITY_ID'].astype(int).astype(str).tolist())
    
    # Build fetch jobs: one per (isin, exchange) pair
    # For dual-listed stocks, create TWO jobs (one NSE, one BSE)
    fetch_jobs = []  # list of (isin, securityId, exchangeSegment, exchange_label)
    seen_isin_exchange = set()
    
    for _, row in stats_df.iterrows():
        isin = row['isin']
        if isin not in isins:
            continue
            
        nse_sym = row.get('nse_symbol')
        bse_code = row.get('bse_code')
        
        # Add NSE job if available
        if pd.notna(nse_sym) and str(nse_sym) in nse_lookup:
            key = (isin, 'NSE')
            if key not in seen_isin_exchange:
                seen_isin_exchange.add(key)
                fetch_jobs.append((isin, str(nse_lookup[str(nse_sym)]), 'NSE_EQ', 'NSE'))
        
        # Add BSE job if available
        if pd.notna(bse_code):
            bse_str = str(int(bse_code))
            if bse_str in bse_valid_codes:
                key = (isin, 'BSE')
                if key not in seen_isin_exchange:
                    seen_isin_exchange.add(key)
                    fetch_jobs.append((isin, bse_str, 'BSE_EQ', 'BSE'))
            
    print(f"Total fetch jobs: {len(fetch_jobs)} (across {len(isins)} ISINs)")

    out_path = repo_root / "temp_dhan_prices_jan23_27.csv"
    
    # Load already-processed (isin, exchange) pairs for resume support
    existing_keys = set()
    if out_path.exists():
        try:
            df_ex = pd.read_csv(out_path)
            if 'isin' in df_ex.columns and 'exchange' in df_ex.columns:
                for _, r in df_ex.iterrows():
                    existing_keys.add((r['isin'], r['exchange']))
                print(f"Loaded {len(existing_keys)} already processed (isin, exchange) pairs.")
        except pd.errors.EmptyDataError:
            pass

    fetch_jobs = [(isin, sid, seg, exch) for isin, sid, seg, exch in fetch_jobs
                  if (isin, exch) not in existing_keys]
    print(f"Remaining jobs to fetch: {len(fetch_jobs)}")

    if len(fetch_jobs) == 0:
        print("All done!")
        return

    url = "https://api.dhan.co/v2/charts/historical"
    headers = {
        "client-id": CLIENT_ID,
        "access-token": ACCESS_TOKEN,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    csv_lock = threading.Lock()
    
    def fetch_one(isin, security_id, exchange_segment, exchange_label):
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": "EQUITY",
            "expiryCode": 0,
            "fromDate": "2026-01-22",
            "toDate": "2026-01-28"
        }
        
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                resp_json = resp.json()
                closes = resp_json.get('close', [])
                timestamps = resp_json.get('timestamp', [])
                
                if not closes or not timestamps:
                    return [{'isin': isin, 'date': 'error', 'dhan_close': None, 'exchange': exchange_label}]
                    
                df_resp = pd.DataFrame({'timestamp': timestamps, 'close': closes})
                df_resp['dt'] = pd.to_datetime(df_resp['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                df_resp['date'] = df_resp['dt'].dt.strftime('%Y-%m-%d')
                df_resp = df_resp[df_resp['date'].isin(['2026-01-22', '2026-01-23', '2026-01-27'])]
                
                if df_resp.empty:
                    return [{'isin': isin, 'date': 'error', 'dhan_close': None, 'exchange': exchange_label}]
                
                fetched = []
                for _, r in df_resp.iterrows():
                    fetched.append({
                        'isin': isin,
                        'date': r['date'],
                        'dhan_close': r['close'],
                        'exchange': exchange_label
                    })
                return fetched
            else:
                return [{'isin': isin, 'date': 'error', 'dhan_close': None, 'exchange': exchange_label}]
        except Exception as e:
            return [{'isin': isin, 'date': 'error', 'dhan_close': None, 'exchange': exchange_label}]

    print("Fetching historical data from Dhan incrementally...")
    count = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {executor.submit(fetch_one, *job): job for job in fetch_jobs}
        for future in as_completed(future_map):
            try:
                data = future.result()
                if data:
                    df_append = pd.DataFrame(data)
                    with csv_lock:
                        write_header = not out_path.exists() or out_path.stat().st_size == 0
                        df_append.to_csv(out_path, mode='a', header=write_header, index=False)
            except Exception as e:
                pass
            count += 1
            if count % 100 == 0:
                print(f"Processed {count}/{len(fetch_jobs)} jobs...")

    print("Fetching completed.")

if __name__ == "__main__":
    fetch_dhan_prices()
