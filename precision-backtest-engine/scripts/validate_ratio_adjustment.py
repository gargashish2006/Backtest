"""
Validates whether the ratio (dhan_close / stored_close on 2026-03-05) is a
uniform multiplier across the full price history.

For each flagged stock with an odd (non-clean-fraction) ratio, fetches Dhan's
actual price at 3 historical reference dates and compares against
stored_price * ratio.

If the ratio holds (within 0.5% tolerance) at all checked dates, ratio-based
adjustment is reliable for that stock.

Output: per-ISIN verdict (RATIO_OK, RATIO_FAIL, NO_REF_DATA) saved to
outputs/ratio_validation_results.csv for use by update_price_data.py.
"""
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT    = Path(__file__).parent.parent
CLIENT_ID    = "1109467957"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzc4NjY4NDgwLCJpYXQiOjE3Nzg1ODIwODAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA5NDY3OTU3In0.EnORSNqpzewl8XfMMAfoS5dQub8Hf9zgn-mNb_7oPwygdJnET2qEknxOShxglLVJ8bDSxFgq9S5retWwPxR7KA"

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {"client-id": CLIENT_ID, "access-token": ACCESS_TOKEN,
           "Accept": "application/json", "Content-Type": "application/json"}

# Reference dates to check — pick 3 well-separated past dates
# Each is (fetch_from, fetch_to, check_date) — Dhan needs a range >1 day
REF_WINDOWS = [
    ("2024-01-03", "2024-01-05", "2024-01-04"),   # ~2 years ago
    ("2023-01-04", "2023-01-06", "2023-01-05"),   # ~3 years ago
    ("2021-06-03", "2021-06-07", "2021-06-04"),   # ~5 years ago
]

RATIO_TOL    = 0.005  # 0.5% tolerance — adjust if needed

# Standard corporate-action ratios — stocks matching these are already trusted
CLEAN_FRACTIONS = [
    1/10, 1/8, 1/5, 1/4, 1/3, 2/5, 1/2, 2/3, 3/4, 4/5,
    5/4, 4/3, 3/2, 2.0, 5/2, 3.0, 4.0, 5.0, 8.0, 10.0,
]
CLEAN_TOL = 0.02

def is_clean_ratio(ratio):
    for frac in CLEAN_FRACTIONS:
        if abs(ratio - frac) / frac <= CLEAN_TOL:
            return True
    return False


def make_session():
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry,
                                    pool_connections=20, pool_maxsize=20))
    return s


def fetch_close(session, security_id, exchange_segment, from_date, to_date, check_date):
    """Return close price on check_date or None."""
    try:
        resp = session.post(URL, headers=HEADERS, json={
            "securityId":      security_id,
            "exchangeSegment": exchange_segment,
            "instrument":      "EQUITY",
            "expiryCode":      0,
            "fromDate":        from_date,
            "toDate":          to_date,
        }, timeout=20)
        if resp.status_code != 200:
            return None
        j = resp.json()
        for ts, c in zip(j.get('timestamp', []), j.get('close', [])):
            dt = pd.to_datetime(ts, unit='s', utc=True).tz_convert('Asia/Kolkata')
            if dt.strftime('%Y-%m-%d') == check_date:
                return float(c)
        return None
    except Exception:
        return None


def main():
    # ---- Load comparison results ----
    comp_raw = pd.read_csv(REPO_ROOT / "outputs/dhan_price_comparison.csv")
    comp_raw['pct_diff'] = comp_raw['pct_diff'].fillna(-1)
    comp = (comp_raw
            .sort_values('pct_diff', ascending=False)
            .drop_duplicates('isin', keep='first'))

    flagged = comp[comp['flagged'] == True].dropna(subset=['dhan_close']).copy()
    flagged['ratio'] = flagged['dhan_close'] / flagged['stored_close']
    flagged['clean'] = flagged['ratio'].apply(is_clean_ratio)

    # Only validate odd-ratio stocks — clean ones are already trusted
    odd = flagged[~flagged['clean']].sort_values('pct_diff', ascending=False).copy()
    print(f"Total flagged ISINs: {len(flagged)}")
    print(f"  Clean ratio (already trusted): {flagged['clean'].sum()}")
    print(f"  Odd ratio (need validation)  : {len(odd)}")

    top = odd
    print(f"\nValidating all {len(top)} odd-ratio stocks:\n")

    # ---- Load stored prices ----
    price_df = pd.read_parquet(REPO_ROOT / "database/price_data.parquet")
    price_df['date'] = pd.to_datetime(price_df['date'])

    # ---- Build security ID map ----
    print("Downloading Dhan scrip master...")
    df_map = pd.read_csv("https://images.dhan.co/api-data/api-scrip-master.csv", low_memory=False)
    df_nse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'NSE') & (df_map['SEM_SEGMENT'] == 'E')]
    df_bse = df_map[(df_map['SEM_EXM_EXCH_ID'] == 'BSE') & (df_map['SEM_SEGMENT'] == 'E')]
    nse_sym_to_sid = df_nse.set_index('SEM_TRADING_SYMBOL')['SEM_SMST_SECURITY_ID'].to_dict()
    bse_valid      = set(df_bse['SEM_SMST_SECURITY_ID'].astype(int).astype(str))

    stats = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")
    stats_idx = stats.set_index('isin')

    def get_sec(isin):
        if isin not in stats_idx.index:
            return None, None
        row = stats_idx.loc[isin]
        # If stats has duplicate ISINs, loc returns a DataFrame — take first row
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        nse_sym = str(row.get('nse_symbol', '')).strip()
        bse_code = row.get('bse_code')
        if nse_sym and nse_sym != 'nan' and nse_sym in nse_sym_to_sid:
            return str(nse_sym_to_sid[nse_sym]), 'NSE_EQ'
        if pd.notna(bse_code):
            bse_str = str(int(bse_code))
            return bse_str, 'BSE_EQ'
        return None, None

    # ---- Fetch historical prices from Dhan ----
    session = make_session()

    # Build all fetch tasks: (isin, ratio, sec_id, seg, ref_window_idx, check_date)
    tasks = []
    for _, row in top.iterrows():
        isin   = row['isin']
        ratio  = row['ratio']
        sec_id, seg = get_sec(isin)
        if not sec_id:
            continue
        for w_idx, (frm, to, chk) in enumerate(REF_WINDOWS):
            tasks.append((isin, ratio, sec_id, seg, w_idx, frm, to, chk))

    print(f"Fetching {len(tasks)} historical prices from Dhan...")

    # (isin, w_idx) -> dhan_ref_close
    dhan_ref = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {
            executor.submit(fetch_close, session, sec_id, seg, frm, to, chk):
            (isin, w_idx)
            for isin, ratio, sec_id, seg, w_idx, frm, to, chk in tasks
        }
        for future in as_completed(future_map):
            key = future_map[future]
            dhan_ref[key] = future.result()

    # ---- Compare stored*ratio vs Dhan historical ----
    print(f"\n{'='*85}")
    print(f"{'ISIN':<15} {'Ratio':>8} {'Date':>12} {'Stored':>9} {'Adj':>9} {'Dhan':>9} {'Err%':>7} {'OK?':>5}")
    print(f"{'='*85}")

    results = []
    for _, row in top.iterrows():
        isin  = row['isin']
        ratio = row['ratio']
        stored_isins = price_df[price_df['isin'] == isin].set_index('date')['close']

        stock_results = {'isin': isin, 'ratio': ratio, 'checks': []}
        for w_idx, (_, _, chk) in enumerate(REF_WINDOWS):
            chk_ts   = pd.Timestamp(chk)
            # Find nearest stored date within ±3 trading days
            nearby = stored_isins.loc[chk_ts - pd.Timedelta(days=5):chk_ts + pd.Timedelta(days=5)]
            if nearby.empty:
                stock_results['checks'].append({'date': chk, 'stored': None, 'dhan': None, 'err_pct': None})
                continue

            # Use closest date to check_date
            nearest_date = min(nearby.index, key=lambda d: abs((d - chk_ts).days))
            stored_close = nearby[nearest_date]
            adjusted     = stored_close * ratio
            dhan_close   = dhan_ref.get((isin, w_idx))

            if dhan_close is not None:
                err_pct = abs(adjusted - dhan_close) / dhan_close * 100
                ok = err_pct <= RATIO_TOL * 100
                print(f"{isin:<15} {ratio:>8.4f} {nearest_date.date()!s:>12} "
                      f"{stored_close:>9.2f} {adjusted:>9.2f} {dhan_close:>9.2f} "
                      f"{err_pct:>6.2f}% {'OK' if ok else 'FAIL':>5}")
                stock_results['checks'].append({
                    'date': str(nearest_date.date()), 'stored': stored_close,
                    'adjusted': adjusted, 'dhan': dhan_close,
                    'err_pct': err_pct, 'ok': ok
                })
            else:
                print(f"{isin:<15} {ratio:>8.4f} {nearest_date.date()!s:>12} "
                      f"{stored_close:>9.2f} {adjusted:>9.2f} {'N/A':>9} {'  N/A':>7} {'  N/A':>5}")
                stock_results['checks'].append({'date': chk, 'stored': stored_close,
                                                'adjusted': adjusted, 'dhan': None, 'err_pct': None})
        results.append(stock_results)

    # ---- Per-ISIN verdict ----
    verdicts = []
    for r in results:
        checks_with_data = [c for c in r['checks'] if c.get('err_pct') is not None]
        checks_passed    = [c for c in checks_with_data if c['ok']]
        checks_failed    = [c for c in checks_with_data if not c['ok']]

        if len(checks_with_data) == 0:
            verdict = 'NO_REF_DATA'
        elif len(checks_failed) == 0:
            verdict = 'RATIO_OK'
        else:
            verdict = 'RATIO_FAIL'

        max_err = max((c['err_pct'] for c in checks_with_data), default=None)
        verdicts.append({
            'isin': r['isin'], 'ratio': r['ratio'],
            'ref_points': len(checks_with_data),
            'passed': len(checks_passed), 'failed': len(checks_failed),
            'max_err_pct': max_err, 'verdict': verdict,
        })

    vdf = pd.DataFrame(verdicts)

    # ---- Summary ----
    print(f"\n{'='*55}")
    print(f"VALIDATION SUMMARY (tolerance = {RATIO_TOL*100:.1f}%)")
    for v in ['RATIO_OK', 'RATIO_FAIL', 'NO_REF_DATA']:
        print(f"  {v:<15}: {(vdf['verdict']==v).sum()}")

    if (vdf['verdict'] == 'RATIO_FAIL').any():
        print(f"\nFailed ISINs:")
        fail_df = vdf[vdf['verdict'] == 'RATIO_FAIL']
        print(fail_df[['isin','ratio','ref_points','passed','failed','max_err_pct']].to_string(index=False))

    if (vdf['verdict'] == 'NO_REF_DATA').any():
        print(f"\nNo ref data ISINs ({(vdf['verdict']=='NO_REF_DATA').sum()}):")
        print(vdf[vdf['verdict'] == 'NO_REF_DATA'][['isin','ratio']].to_string(index=False))

    # Save for use by update_price_data.py
    out_path = REPO_ROOT / "outputs/ratio_validation_results.csv"
    vdf.to_csv(out_path, index=False)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
