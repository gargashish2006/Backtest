"""
Compares last stored close (2026-03-05) in price_data.parquet against
Dhan API close for the same date.

Stocks with |pct_diff| > 0.1% are flagged as likely corporate action affected
and will need a full re-fetch rather than an incremental append.
"""
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT = Path(__file__).parent.parent

CLIENT_ID    = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc4NTc4MjIxLCJpYXQiOjE3Nzg0OTE4MjEsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.1c8atw5WKdOc2IT1qnoJCbyldNLSuurpAHxczsY9K7XrKj39QHd5qyV2elkdbCMtfi7NTZELDHiArfXMO2d9uQ"

CHECK_DATE  = "2026-03-05"
FETCH_FROM  = "2026-03-03"   # small range — Dhan needs >1 day
FETCH_TO    = "2026-03-07"
THRESHOLD   = 0.001   # 0.1%
OUT_CSV     = REPO_ROOT / "outputs/dhan_price_comparison.csv"

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {
    "client-id": CLIENT_ID,
    "access-token": ACCESS_TOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def build_security_map(stats_df):
    """Download Dhan scrip master and return ISIN -> list of (security_id, exchange_segment)."""
    print("Downloading Dhan scrip master...")
    df_map = pd.read_csv("https://images.dhan.co/api-data/api-scrip-master.csv", low_memory=False)
    print(f"  {len(df_map)} records downloaded.")

    df_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    df_bse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'BSE') & (df_map['SEM_SEGMENT'] == 'E')]

    nse_lookup = df_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    bse_valid  = set(df_bse['SEM_SMST_SECURITY_ID'].astype(int).astype(str))

    jobs = []
    for _, row in stats_df.iterrows():
        isin     = row['isin']
        nse_sym  = row.get('nse_symbol')
        bse_code = row.get('bse_code')

        if pd.notna(nse_sym) and str(nse_sym) in nse_lookup:
            jobs.append((isin, str(nse_lookup[str(nse_sym)]), 'NSE_EQ', 'NSE'))

        if pd.notna(bse_code):
            bse_str = str(int(bse_code))
            if bse_str in bse_valid:
                jobs.append((isin, bse_str, 'BSE_EQ', 'BSE'))

    return jobs


def fetch_one(session, isin, security_id, exchange_segment, exchange_label, check_date):
    payload = {
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": FETCH_FROM,
        "toDate": FETCH_TO,
    }
    try:
        resp = session.post(URL, headers=HEADERS, json=payload, timeout=20)
        if resp.status_code != 200:
            return None
        j = resp.json()
        closes     = j.get('close', [])
        timestamps = j.get('timestamp', [])
        if not closes or not timestamps:
            return None
        for ts, c in zip(timestamps, closes):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            if dt.strftime('%Y-%m-%d') == check_date:
                return {'isin': isin, 'exchange': exchange_label, 'dhan_close': float(c)}
        return None
    except Exception:
        return None


def main():
    # Load stored prices for CHECK_DATE
    print(f"Loading price_data.parquet...")
    price_df = pd.read_parquet(REPO_ROOT / "database/price_data.parquet")
    price_df['date'] = pd.to_datetime(price_df['date'])
    stored = price_df[price_df['date'] == pd.Timestamp(CHECK_DATE)][['isin', 'close', 'exchange']]\
        .rename(columns={'close': 'stored_close'})
    print(f"  {len(stored)} rows on {CHECK_DATE} across {stored['isin'].nunique()} stocks.")

    # Load stock_statistics for NSE symbol / BSE code
    stats_df = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")

    # Build fetch jobs
    jobs = build_security_map(stats_df)
    # Only fetch ISINs we actually have stored prices for
    stored_isins = set(stored['isin'].unique())
    jobs = [(isin, sid, seg, exch) for isin, sid, seg, exch in jobs if isin in stored_isins]
    print(f"  {len(jobs)} fetch jobs for {len(stored_isins)} ISINs.")

    # Fetch from Dhan (parallel)
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=30, pool_maxsize=30))

    results = []
    lock = threading.Lock()
    count = 0

    print("Fetching prices from Dhan API...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_map = {
            executor.submit(fetch_one, session, *job, CHECK_DATE): job
            for job in jobs
        }
        for future in as_completed(future_map):
            count += 1
            row = future.result()
            if row:
                with lock:
                    results.append(row)
            if count % 500 == 0:
                print(f"  {count}/{len(jobs)} done, {len(results)} fetched...")

    print(f"  Fetched {len(results)} Dhan prices.")

    if not results:
        print("No data fetched from Dhan. Check token / network.")
        return

    dhan_df = pd.DataFrame(results)

    # Merge stored vs Dhan — prefer NSE, fall back to BSE
    dhan_nse = dhan_df[dhan_df['exchange'] == 'NSE'].rename(columns={'dhan_close': 'dhan_nse'})
    dhan_bse = dhan_df[dhan_df['exchange'] == 'BSE'].rename(columns={'dhan_close': 'dhan_bse'})

    comp = stored.merge(dhan_nse[['isin', 'dhan_nse']], on='isin', how='left')
    comp = comp.merge(dhan_bse[['isin', 'dhan_bse']], on='isin', how='left')

    # Use NSE if available, else BSE
    comp['dhan_close'] = comp['dhan_nse'].combine_first(comp['dhan_bse'])
    comp['pct_diff']   = ((comp['dhan_close'] - comp['stored_close']) / comp['stored_close']).abs() * 100
    comp['flagged']    = comp['pct_diff'] > (THRESHOLD * 100)

    # Save full comparison
    OUT_CSV.parent.mkdir(exist_ok=True)
    comp.to_csv(OUT_CSV, index=False)
    print(f"\nSaved comparison to {OUT_CSV}")

    # Summary
    matched    = comp[comp['flagged'] == False].dropna(subset=['dhan_close'])
    flagged    = comp[comp['flagged'] == True].dropna(subset=['dhan_close'])
    no_dhan    = comp[comp['dhan_close'].isna()]

    print(f"\n{'='*55}")
    print(f"PRICE COMPARISON SUMMARY  (threshold = {THRESHOLD*100}%)")
    print(f"{'='*55}")
    print(f"  Total stocks checked   : {comp['isin'].nunique()}")
    print(f"  Matched (safe append)  : {matched['isin'].nunique()}")
    print(f"  Flagged (corp action?) : {flagged['isin'].nunique()}")
    print(f"  No Dhan data found     : {no_dhan['isin'].nunique()}")

    if not flagged.empty:
        print(f"\nFlagged stocks (top 30 by pct_diff):")
        print(f"  {'ISIN':<15} {'Stored':>10} {'Dhan':>10} {'Diff%':>8}")
        print(f"  {'-'*47}")
        for _, r in flagged.sort_values('pct_diff', ascending=False).head(30).iterrows():
            print(f"  {r['isin']:<15} {r['stored_close']:>10.2f} {r['dhan_close']:>10.2f} {r['pct_diff']:>7.2f}%")


if __name__ == "__main__":
    main()
