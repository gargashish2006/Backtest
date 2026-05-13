"""
Retry price comparison for the 483 stocks still missing Dhan data.
Tries both NSE_EQ and BSE_EQ for each stock, prefers NSE if both return data.
Appends results to outputs/dhan_price_comparison.csv.
"""
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT    = Path(__file__).parent.parent
CLIENT_ID    = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc4NjY4NDgwLCJpYXQiOjE3Nzg1ODIwODAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.EnORSNqpzewl8XfMMAfoS5dQub8Hf9zgn-mNb_7oPwygdJnET2qEknxOShxglLVJ8bDSxFgq9S5retWwPxR7KA"

CHECK_DATE = "2026-03-05"
FETCH_FROM = "2026-03-03"
FETCH_TO   = "2026-03-07"
THRESHOLD  = 0.001

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {"client-id": CLIENT_ID, "access-token": ACCESS_TOKEN,
           "Accept": "application/json", "Content-Type": "application/json"}


def fetch_price(session, security_id, exchange_segment):
    """Returns close on CHECK_DATE or None."""
    try:
        resp = session.post(URL, headers=HEADERS, json={
            "securityId": security_id, "exchangeSegment": exchange_segment,
            "instrument": "EQUITY", "expiryCode": 0,
            "fromDate": FETCH_FROM, "toDate": FETCH_TO,
        }, timeout=20)
        if resp.status_code != 200:
            return None
        j = resp.json()
        for ts, c in zip(j.get('timestamp', []), j.get('close', [])):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            if dt.strftime('%Y-%m-%d') == CHECK_DATE:
                return float(c)
        return None
    except Exception:
        return None


def fetch_stock(session, isin, nse_sid, bse_sid):
    """Try NSE first, then BSE. Return (isin, close, exchange) or None."""
    if nse_sid:
        c = fetch_price(session, nse_sid, 'NSE_EQ')
        if c is not None:
            return {'isin': isin, 'dhan_close': c, 'exchange': 'NSE'}
    if bse_sid:
        c = fetch_price(session, bse_sid, 'BSE_EQ')
        if c is not None:
            return {'isin': isin, 'dhan_close': c, 'exchange': 'BSE'}
    return None


def main():
    comp_path = REPO_ROOT / "outputs/dhan_price_comparison.csv"
    comp = pd.read_csv(comp_path)
    no_data = comp[comp['dhan_close'].isna()][['isin', 'stored_close']].drop_duplicates('isin')
    print(f"Stocks to retry: {len(no_data)}")

    stats = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")
    targets = no_data.merge(stats[['isin', 'nse_symbol', 'bse_code']], on='isin', how='left')

    # Download scrip master for NSE security IDs
    print("Downloading Dhan scrip master...")
    df_map = pd.read_csv("https://images.dhan.co/api-data/api-scrip-master.csv", low_memory=False)
    df_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    nse_sym_to_sid = df_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    print(f"  {len(nse_sym_to_sid)} NSE symbols loaded.")

    # Build jobs: (isin, nse_sid, bse_sid)
    jobs = []
    for _, row in targets.iterrows():
        nse_sym = row.get('nse_symbol')
        bse_code = row.get('bse_code')
        nse_sym_clean = str(nse_sym).strip() if pd.notna(nse_sym) else None
        nse_sid = str(nse_sym_to_sid[nse_sym_clean]) if nse_sym_clean and nse_sym_clean in nse_sym_to_sid else None
        bse_sid = str(int(bse_code)) if pd.notna(bse_code) else None
        jobs.append((row['isin'], nse_sid, bse_sid))

    covered = sum(1 for _, n, b in jobs if n or b)
    print(f"  {covered}/{len(jobs)} stocks have at least one identifier.")

    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"])
    session.mount("https://", HTTPAdapter(max_retries=retry,
                                          pool_connections=30, pool_maxsize=30))

    results = []
    lock = threading.Lock()
    count = 0

    print(f"Fetching {len(jobs)} stocks (NSE preferred, BSE fallback)...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_map = {executor.submit(fetch_stock, session, isin, nse_sid, bse_sid): isin
                      for isin, nse_sid, bse_sid in jobs}
        for future in as_completed(future_map):
            count += 1
            row = future.result()
            if row:
                with lock:
                    results.append(row)
            if count % 100 == 0:
                print(f"  {count}/{len(jobs)} done, {len(results)} fetched...")

    print(f"  Fetched {len(results)} prices.")

    if not results:
        print("Nothing fetched.")
        return

    dhan_df = pd.DataFrame(results)

    # Merge with stored prices
    new_comp = no_data.merge(dhan_df[['isin', 'dhan_close']], on='isin', how='left')
    new_comp['pct_diff'] = ((new_comp['dhan_close'] - new_comp['stored_close'])
                            / new_comp['stored_close']).abs() * 100
    new_comp['flagged'] = new_comp['pct_diff'] > (THRESHOLD * 100)

    # Update master comparison CSV
    comp = comp.set_index('isin')
    for _, r in new_comp.dropna(subset=['dhan_close']).iterrows():
        if r['isin'] in comp.index:
            comp.at[r['isin'], 'dhan_close'] = r['dhan_close']
            comp.at[r['isin'], 'pct_diff']   = r['pct_diff']
            comp.at[r['isin'], 'flagged']     = r['flagged']
    comp = comp.reset_index()
    comp.to_csv(comp_path, index=False)
    print(f"\nUpdated {comp_path}")

    matched     = new_comp[new_comp['flagged'] == False].dropna(subset=['dhan_close'])
    flagged     = new_comp[new_comp['flagged'] == True].dropna(subset=['dhan_close'])
    still_miss  = new_comp[new_comp['dhan_close'].isna()]

    print(f"\n{'='*55}")
    print(f"RETRY SUMMARY  (threshold = 0.1%)")
    print(f"{'='*55}")
    print(f"  Matched (safe append)  : {len(matched)}")
    print(f"  Flagged (corp action?) : {len(flagged)}")
    print(f"  Still no data          : {len(still_miss)}")

    # Final overall tally
    comp_final = pd.read_csv(comp_path)
    print(f"\nOVERALL TOTALS:")
    print(f"  Safe append  : {(comp_final['flagged']==False).sum()}")
    print(f"  Flagged      : {(comp_final['flagged']==True).sum()}")
    print(f"  No data      : {comp_final['dhan_close'].isna().sum()}")

    if not still_miss.empty:
        print(f"\nStill missing ISINs (first 20):")
        miss_info = still_miss.merge(stats[['isin','company_name','nse_symbol','bse_code']], on='isin', how='left')
        for _, r in miss_info.head(20).iterrows():
            print(f"  {r['isin']}  {r.get('company_name','')[:35]}  nse={r.get('nse_symbol','')}  bse={r.get('bse_code','')}")


if __name__ == "__main__":
    main()
