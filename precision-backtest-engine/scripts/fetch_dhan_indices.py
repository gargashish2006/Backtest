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

def fetch_indices():
    # Define indices and their Dhan Security IDs
    target_indices = {
        'NIFTY 50': '13',
        'NIFTY 100': '17',
        'NIFTY 200': '18',
        'NIFTY 500': '19',
        'NIFTY MIDCAP 100': '442',  # MIDCPNIFTY
        'NIFTY MIDCAP 150': '1',
        'NIFTY SMALLCAP 100': '5',
        'NIFTY LARGEMID250': '6',
        'NIFTY SMALLCAP 250': '3'
    }
    
    print(f"Fetching {len(target_indices)} indices...")
    
    # Needs two chunks due to 2000 candle limit
    # Chunk 1: 2016-02-01 to 2021-06-30
    # Chunk 2: 2021-07-01 to 2026-03-06
    chunks = [
        ('2016-02-01', '2021-06-30'),
        ('2021-07-01', '2026-03-06')
    ]
    
    fetch_jobs = []
    seen = set()
    
    for idx_name, sec_id in target_indices.items():
        for chunk_id, (fd, td) in enumerate(chunks):
            key = (idx_name, sec_id, f'chunk_{chunk_id}')
            if key not in seen:
                seen.add(key)
                fetch_jobs.append((idx_name, sec_id, 'IDX_I', fd, td, f'chunk_{chunk_id}'))
                
    print(f"Total fetch jobs created: {len(fetch_jobs)}")
    
    out_path = repo_root / "database/indices_data.parquet"
    temp_csv_path = repo_root / "temp_dhan_indices.csv"
    
    # Clear temp if exists
    if temp_csv_path.exists():
        temp_csv_path.unlink()
    
    # Setup session
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
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    csv_lock = threading.Lock()
    
    def fetch_one(idx_name, security_id, exchange_segment, from_date, to_date, chunk_id):
        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": "INDEX",
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
                timestamps = resp_json.get('timestamp', [])
                
                if not closes or not timestamps:
                    return [{'index_name': idx_name, 'date': 'error', 'open': None, 'high': None,
                             'low': None, 'close': None, 'chunk_id': chunk_id}]
                
                records = []
                for i in range(len(timestamps)):
                    dt = pd.to_datetime(timestamps[i], unit='s', utc=True).tz_convert('Asia/Kolkata')
                    records.append({
                        'index_name': idx_name,
                        'date': dt.strftime('%Y-%m-%d'),
                        'open': opens[i] if i < len(opens) else None,
                        'high': highs[i] if i < len(highs) else None,
                        'low': lows[i] if i < len(lows) else None,
                        'close': closes[i] if i < len(closes) else None,
                        'chunk_id': chunk_id
                    })
                return records
            else:
                return [{'index_name': idx_name, 'date': 'error', 'open': None, 'high': None,
                         'low': None, 'close': None, 'chunk_id': chunk_id}]
        except Exception as e:
            return [{'index_name': idx_name, 'date': 'error', 'open': None, 'high': None,
                     'low': None, 'close': None, 'chunk_id': chunk_id}]

    # Run fetches
    print("Fetching index data from Dhan incrementally...")
    count = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
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
            if count % 5 == 0:
                print(f"Processed {count}/{len(fetch_jobs)} jobs...")
                
    print("Fetching completed. Converting to parquet...")
    
    # Convert and clean
    df = pd.read_csv(temp_csv_path)
    df = df[df['index_name'] != 'index_name'].copy()
    df = df[df['date'] != 'error'].copy()
    
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])
    
    df = df.drop(columns=['chunk_id'], errors='ignore')
    df = df.drop_duplicates(subset=['index_name', 'date'], keep='first')
    df = df.sort_values(['index_name', 'date']).reset_index(drop=True)
    
    df.to_parquet(out_path, index=False)
    print(f"Saved {len(df)} records to {out_path}")
    print("\nSummary:")
    for idx in df['index_name'].unique():
        sub = df[df['index_name'] == idx]
        print(f"  {idx}: {len(sub)} rows, {sub['date'].min().date()} to {sub['date'].max().date()}")
    
    # Cleanup temp
    temp_csv_path.unlink()

if __name__ == "__main__":
    fetch_indices()
