"""
Incremental updater for indices_data.parquet.
Fetches only the missing date range from Dhan API and appends to existing data.
"""
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT = Path(__file__).parent.parent

CLIENT_ID   = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc4NjY4NDgwLCJpYXQiOjE3Nzg1ODIwODAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.EnORSNqpzewl8XfMMAfoS5dQub8Hf9zgn-mNb_7oPwygdJnET2qEknxOShxglLVJ8bDSxFgq9S5retWwPxR7KA"

INDICES = {
    'NIFTY 50':          '13',
    'NIFTY 100':         '17',
    'NIFTY 200':         '18',
    'NIFTY 500':         '19',
    'NIFTY MIDCAP 100':  '442',
    'NIFTY MIDCAP 150':  '1',
    'NIFTY SMALLCAP 100':'5',
    'NIFTY LARGEMID250': '6',
    'NIFTY SMALLCAP 250':'3',
}

FROM_DATE = "2026-03-06"
TO_DATE   = "2026-05-13"
OUT_PATH  = REPO_ROOT / "database/indices_data.parquet"

URL = "https://api.dhan.co/v2/charts/historical"
HEADERS = {
    "client-id": CLIENT_ID,
    "access-token": ACCESS_TOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def fetch_one(session, idx_name, sec_id, from_date, to_date):
    payload = {
        "securityId": sec_id,
        "exchangeSegment": "IDX_I",
        "instrument": "INDEX",
        "expiryCode": 0,
        "fromDate": from_date,
        "toDate": to_date,
    }
    try:
        resp = session.post(URL, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR {idx_name}: HTTP {resp.status_code} — {resp.text[:200]}")
            return []
        j = resp.json()
        closes     = j.get('close', [])
        opens      = j.get('open', [])
        highs      = j.get('high', [])
        lows       = j.get('low', [])
        timestamps = j.get('timestamp', [])
        if not closes or not timestamps:
            print(f"  WARN {idx_name}: empty response")
            return []
        records = []
        for i, ts in enumerate(timestamps):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            records.append({
                'index_name': idx_name,
                'date':  dt.strftime('%Y-%m-%d'),
                'open':  opens[i]  if i < len(opens)  else None,
                'high':  highs[i]  if i < len(highs)  else None,
                'low':   lows[i]   if i < len(lows)   else None,
                'close': closes[i],
            })
        return records
    except Exception as e:
        print(f"  EXCEPTION {idx_name}: {e}")
        return []


def main():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    print(f"Fetching {len(INDICES)} indices from {FROM_DATE} to {TO_DATE}...")

    all_records = []
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = {
            executor.submit(fetch_one, session, name, sid, FROM_DATE, TO_DATE): name
            for name, sid in INDICES.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            records = future.result()
            with lock:
                all_records.extend(records)
            print(f"  {name}: {len(records)} rows fetched")

    if not all_records:
        print("No data fetched. Check token / dates.")
        return

    new_df = pd.DataFrame(all_records)
    new_df['date'] = pd.to_datetime(new_df['date'])
    for col in ['open', 'high', 'low', 'close']:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')

    # Load existing and merge
    existing = pd.read_parquet(OUT_PATH)
    existing['date'] = pd.to_datetime(existing['date'])

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=['index_name', 'date'], keep='last')
    combined = combined.sort_values(['index_name', 'date']).reset_index(drop=True)
    combined.to_parquet(OUT_PATH, index=False)

    print(f"\nUpdated {OUT_PATH}")
    print("\nNew date ranges:")
    for name, grp in combined.groupby('index_name'):
        print(f"  {name:<25} {grp['date'].min().date()} to {grp['date'].max().date()}  ({len(grp)} rows)")


if __name__ == "__main__":
    main()
