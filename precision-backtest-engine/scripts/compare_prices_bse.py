"""
Price comparison for the 1186 stocks that had no Dhan data in the first pass.
Fetches directly using BSE code as security_id (bypasses scrip master filter).
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
THRESHOLD  = 0.001  # 0.1%

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {"client-id": CLIENT_ID, "access-token": ACCESS_TOKEN,
           "Accept": "application/json", "Content-Type": "application/json"}


def fetch_one(session, isin, bse_str):
    try:
        resp = session.post(URL, headers=HEADERS, json={
            "securityId": bse_str, "exchangeSegment": "BSE_EQ",
            "instrument": "EQUITY", "expiryCode": 0,
            "fromDate": FETCH_FROM, "toDate": FETCH_TO,
        }, timeout=20)
        if resp.status_code != 200:
            return None
        j = resp.json()
        closes, timestamps = j.get('close', []), j.get('timestamp', [])
        if not closes:
            return None
        for ts, c in zip(timestamps, closes):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            if dt.strftime('%Y-%m-%d') == CHECK_DATE:
                return {'isin': isin, 'exchange': 'BSE', 'dhan_close': float(c)}
        return None
    except Exception:
        return None


def main():
    # Load existing comparison — get no-dhan ISINs
    comp_path = REPO_ROOT / "outputs/dhan_price_comparison.csv"
    comp = pd.read_csv(comp_path)
    no_dhan = comp[comp['dhan_close'].isna()][['isin', 'stored_close']].drop_duplicates('isin')
    print(f"No-Dhan stocks to retry: {len(no_dhan)}")

    # Get BSE codes for these ISINs
    stats = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")
    targets = no_dhan.merge(stats[['isin', 'bse_code', 'nse_symbol']], on='isin', how='left')
    has_bse = targets[targets['bse_code'].notna()].copy()
    has_bse['bse_str'] = has_bse['bse_code'].astype(int).astype(str)
    print(f"  With BSE code: {len(has_bse)}, Without: {len(targets) - len(has_bse)}")

    session = requests.Session()
    retry = Retry(total=4, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"])
    session.mount("https://", HTTPAdapter(max_retries=retry,
                                          pool_connections=30, pool_maxsize=30))

    results = []
    lock = threading.Lock()
    count = 0
    jobs = [(row['isin'], row['bse_str']) for _, row in has_bse.iterrows()]

    print(f"Fetching {len(jobs)} stocks from Dhan BSE...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_map = {executor.submit(fetch_one, session, isin, bse): (isin, bse)
                      for isin, bse in jobs}
        for future in as_completed(future_map):
            count += 1
            row = future.result()
            if row:
                with lock:
                    results.append(row)
            if count % 200 == 0:
                print(f"  {count}/{len(jobs)} done, {len(results)} fetched...")

    print(f"  Fetched {len(results)} prices.")

    if not results:
        print("Nothing fetched — check token.")
        return

    dhan_df = pd.DataFrame(results)

    # Merge with stored prices
    new_comp = no_dhan.merge(dhan_df[['isin', 'dhan_close']], on='isin', how='left')
    new_comp['pct_diff'] = ((new_comp['dhan_close'] - new_comp['stored_close'])
                            / new_comp['stored_close']).abs() * 100
    new_comp['flagged'] = new_comp['pct_diff'] > (THRESHOLD * 100)

    # Update the master comparison: fill in dhan_close for previously-missing rows
    comp = comp.set_index('isin')
    for _, r in new_comp.dropna(subset=['dhan_close']).iterrows():
        if r['isin'] in comp.index:
            comp.at[r['isin'], 'dhan_close'] = r['dhan_close']
            comp.at[r['isin'], 'pct_diff']   = r['pct_diff']
            comp.at[r['isin'], 'flagged']     = r['flagged']
    comp = comp.reset_index()
    comp.to_csv(comp_path, index=False)
    print(f"\nUpdated {comp_path}")

    # Summary
    matched = new_comp[new_comp['flagged'] == False].dropna(subset=['dhan_close'])
    flagged = new_comp[new_comp['flagged'] == True].dropna(subset=['dhan_close'])
    still_missing = new_comp[new_comp['dhan_close'].isna()]

    print(f"\n{'='*55}")
    print(f"BSE PRICE COMPARISON SUMMARY  (threshold = 0.1%)")
    print(f"{'='*55}")
    print(f"  Matched (safe append)  : {len(matched)}")
    print(f"  Flagged (corp action?) : {len(flagged)}")
    print(f"  Still no data          : {len(still_missing)}")

    if not flagged.empty:
        print(f"\nFlagged stocks (top 20 by pct_diff):")
        print(f"  {'ISIN':<15} {'Stored':>10} {'Dhan':>10} {'Diff%':>8}")
        print(f"  {'-'*47}")
        for _, r in flagged.sort_values('pct_diff', ascending=False).head(20).iterrows():
            print(f"  {r['isin']:<15} {r['stored_close']:>10.2f} "
                  f"{r['dhan_close']:>10.2f} {r['pct_diff']:>7.2f}%")


if __name__ == "__main__":
    main()
