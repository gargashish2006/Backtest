"""
Fix: Re-fetch incremental data (2026-03-06 to 2026-05-13) for all safe-append
stocks that are missing data after 2026-03-05 in price_data.parquet.

These were supposed to be updated by update_price_data.py but their rows
didn't survive into the final parquet.
"""
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT    = Path(__file__).parent.parent
CLIENT_ID    = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc4NjY4NDgwLCJpYXQiOjE3Nzg1ODIwODAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.EnORSNqpzewl8XfMMAfoS5dQub8Hf9zgn-mNb_7oPwygdJnET2qEknxOShxglLVJ8bDSxFgq9S5retWwPxR7KA"

FROM_DATE = "2026-03-06"
TO_DATE   = "2026-05-13"

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {"client-id": CLIENT_ID, "access-token": ACCESS_TOKEN,
           "Accept": "application/json", "Content-Type": "application/json"}

PRICE_PATH = REPO_ROOT / "database/price_data.parquet"


def make_session():
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry,
                                    pool_connections=40, pool_maxsize=40))
    return s


def fetch_ohlcv(session, security_id, exchange_segment, from_date, to_date):
    try:
        resp = session.post(URL, headers=HEADERS, json={
            "securityId":      security_id,
            "exchangeSegment": exchange_segment,
            "instrument":      "EQUITY",
            "expiryCode":      0,
            "fromDate":        from_date,
            "toDate":          to_date,
        }, timeout=30)
        if resp.status_code != 200:
            return []
        j = resp.json()
        timestamps = j.get('timestamp', [])
        closes     = j.get('close',     [])
        opens      = j.get('open',      [])
        highs      = j.get('high',      [])
        lows       = j.get('low',       [])
        volumes    = j.get('volume',    [])
        if not timestamps or not closes:
            return []
        records = []
        for i, ts in enumerate(timestamps):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            records.append({
                'date':   dt.strftime('%Y-%m-%d'),
                'open':   opens[i]   if i < len(opens)   else None,
                'high':   highs[i]   if i < len(highs)   else None,
                'low':    lows[i]    if i < len(lows)     else None,
                'close':  closes[i],
                'volume': volumes[i] if i < len(volumes)  else None,
            })
        return records
    except Exception:
        return []


def build_security_map(stats_df):
    print("Downloading Dhan scrip master...")
    df_map = pd.read_csv("https://images.dhan.co/api-data/api-scrip-master.csv",
                         low_memory=False)
    df_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    df_bse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'BSE') & (df_map['SEM_SEGMENT'] == 'E')]
    nse_sym_to_sid = df_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    bse_valid      = set(df_bse['SEM_SMST_SECURITY_ID'].astype(int).astype(str))
    print(f"  {len(nse_sym_to_sid)} NSE + {len(bse_valid)} BSE securities loaded.")

    stats_idx = stats_df.drop_duplicates('isin').set_index('isin')
    isin_map = {}
    for isin, row in stats_idx.iterrows():
        nse_sym  = str(row.get('nse_symbol', '')).strip()
        bse_code = row.get('bse_code')
        if nse_sym and nse_sym != 'nan' and nse_sym in nse_sym_to_sid:
            isin_map[isin] = (str(nse_sym_to_sid[nse_sym]), 'NSE_EQ', 'NSE')
        elif pd.notna(bse_code):
            isin_map[isin] = (str(int(bse_code)), 'BSE_EQ', 'BSE')
    return isin_map


def main():
    # Load price data
    print("Loading price_data.parquet...")
    existing = pd.read_parquet(PRICE_PATH)
    existing['date'] = pd.to_datetime(existing['date'])
    print(f"  {len(existing):,} rows, up to {existing['date'].max().date()}")

    # Find all ISINs missing data after Mar 5
    after_mar5_isins = set(existing[existing['date'] > '2026-03-05']['isin'].unique())
    all_isins = set(existing['isin'].unique())
    missing_isins = all_isins - after_mar5_isins
    print(f"\nISINs missing data after 2026-03-05: {len(missing_isins)}")
    print(f"ISINs already up to date: {len(after_mar5_isins)}")

    # Build security ID map
    stats = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")
    isin_map = build_security_map(stats)

    # Build fetch jobs
    jobs = []
    skipped = 0
    for isin in missing_isins:
        if isin in isin_map:
            sid, seg, exch = isin_map[isin]
            jobs.append((isin, sid, seg, exch))
        else:
            skipped += 1
    print(f"\nJobs to fetch: {len(jobs)}, skipped (no ID): {skipped}")

    # Parallel fetch
    session  = make_session()
    all_rows = []
    lock     = threading.Lock()
    count    = 0

    isin_to_exch = {isin: exch for isin, sid, seg, exch in jobs}

    with ThreadPoolExecutor(max_workers=40) as executor:
        future_map = {
            executor.submit(fetch_ohlcv, session, sid, seg, FROM_DATE, TO_DATE): (isin, exch)
            for isin, sid, seg, exch in jobs
        }
        for future in as_completed(future_map):
            isin, exch = future_map[future]
            count += 1
            rows = future.result()
            if rows:
                for r in rows:
                    r['isin']     = isin
                    r['exchange'] = exch
                with lock:
                    all_rows.extend(rows)
            if count % 500 == 0 or count == len(jobs):
                print(f"  {count}/{len(jobs)} done — {len(all_rows)} rows fetched")

    print(f"\nTotal new rows fetched: {len(all_rows)}")
    if not all_rows:
        print("Nothing fetched — check token/API.")
        return

    new_df = pd.DataFrame(all_rows)
    new_df['date'] = pd.to_datetime(new_df['date'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')

    # Only keep rows strictly after existing last date for each ISIN
    existing_last = existing.groupby('isin')['date'].max()
    cutoff_map = new_df['isin'].map(existing_last).fillna(pd.Timestamp('1900-01-01'))
    new_df = new_df[new_df['date'] > cutoff_map].copy()
    print(f"After cutoff filter: {len(new_df)} truly new rows")

    # Append and save — no dedup needed; cutoff filter already ensures no date overlap
    new_df['date'] = new_df['date'].astype('datetime64[ns]')
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values(['isin', 'date']).reset_index(drop=True)

    print(f"\nFinal rows   : {len(combined):,}")
    print(f"Unique stocks: {combined['isin'].nunique()}")
    print(f"Date range   : {combined['date'].min().date()} to {combined['date'].max().date()}")
    last_by_exch = combined.groupby('exchange')['date'].max()
    print("\nLast date by exchange:")
    for exch, dt in last_by_exch.items():
        print(f"  {exch}: {dt.date()}")

    combined.to_parquet(PRICE_PATH, index=False)
    print(f"\nSaved -> {PRICE_PATH}")


if __name__ == "__main__":
    main()
