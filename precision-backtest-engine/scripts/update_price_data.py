"""
Updates price_data.parquet to 2026-05-12.

Three modes per stock:
  safe-append  — no corporate action; fetch only 2026-03-06 → 2026-05-08 and append.
  ratio-adjust — clean corporate action (split/bonus); multiply all stored history by
                 ratio (dhan_close / stored_close on 2026-03-05), then append incremental.
  full-refetch — odd ratio or pricing anomaly; drop stored data and re-fetch full history.
  no-data      — not in Dhan; leave untouched.

Classification uses outputs/dhan_price_comparison.csv produced by the compare_prices_*.py
scripts. A ratio is "clean" if it lies within 2% of a standard corporate-action fraction
(1/10, 1/5, 1/4, 1/3, 1/2, 2/3, 3/4, 2, 3, 4, 5, 10).
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

INCREMENTAL_FROM = "2026-03-06"
INCREMENTAL_TO   = "2026-05-12"
FULL_FROM        = "2017-01-01"
FULL_TO          = "2026-05-12"

URL     = "https://api.dhan.co/v2/charts/historical"
HEADERS = {"client-id": CLIENT_ID, "access-token": ACCESS_TOKEN,
           "Accept": "application/json", "Content-Type": "application/json"}

PRICE_PATH = REPO_ROOT / "database/price_data.parquet"
COMP_PATH  = REPO_ROOT / "outputs/dhan_price_comparison.csv"

# Standard corporate-action ratios (new_price / old_price)
CLEAN_FRACTIONS = [
    1/10, 1/8, 1/5, 1/4, 1/3, 2/5, 1/2, 2/3, 3/4, 4/5,
    5/4, 4/3, 3/2, 2.0, 5/2, 3.0, 4.0, 5.0, 8.0, 10.0,
]
CLEAN_TOL = 0.02   # 2% tolerance for matching a standard fraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_clean_ratio(ratio):
    """Return True if ratio is within CLEAN_TOL of any standard fraction."""
    for frac in CLEAN_FRACTIONS:
        if abs(ratio - frac) / frac <= CLEAN_TOL:
            return True
    return False


def make_session():
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry,
                                    pool_connections=40, pool_maxsize=40))
    return s


def fetch_ohlcv(session, security_id, exchange_segment, from_date, to_date):
    """Return list of OHLCV dicts or []."""
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


def fetch_for_isin(session, isin, security_id, exchange_segment, exchange_label,
                   from_date, to_date):
    rows = fetch_ohlcv(session, security_id, exchange_segment, from_date, to_date)
    for r in rows:
        r['isin']     = isin
        r['exchange'] = exchange_label
    return rows


# ---------------------------------------------------------------------------
# Security ID map
# ---------------------------------------------------------------------------

def build_security_map(stats_df):
    """isin -> (security_id, exchange_segment, exchange_label). Prefers NSE."""
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


# ---------------------------------------------------------------------------
# Parallel fetch helper
# ---------------------------------------------------------------------------

def parallel_fetch(session, jobs, desc, workers=40):
    """
    jobs: list of (isin, sec_id, seg, exch, from_date, to_date)
    Returns list of all row dicts fetched.
    """
    results = []
    lock    = threading.Lock()
    count   = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(fetch_for_isin, session, isin, sid, seg, exch, frm, to): isin
            for isin, sid, seg, exch, frm, to in jobs
        }
        for future in as_completed(future_map):
            count += 1
            rows = future.result()
            if rows:
                with lock:
                    results.extend(rows)
            if count % 500 == 0 or count == len(jobs):
                print(f"  [{desc}] {count}/{len(jobs)} done — {len(results)} rows so far")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ── Load comparison ──────────────────────────────────────────────────────
    # The CSV may have multiple rows per ISIN (NSE + BSE).  Keep the worst-
    # case row (highest pct_diff) so that an ISIN flagged on *any* exchange
    # is treated as flagged.
    comp_raw = pd.read_csv(COMP_PATH)
    comp_raw['pct_diff'] = comp_raw['pct_diff'].fillna(-1)          # no-data rows get -1
    comp = (comp_raw
            .sort_values('pct_diff', ascending=False)
            .drop_duplicates('isin', keep='first')
            .copy())
    comp['ratio'] = comp['dhan_close'] / comp['stored_close']

    safe_isins    = set(comp[comp['flagged'] == False]['isin'].dropna())
    no_data_isins = set(comp[comp['dhan_close'].isna()]['isin'].dropna())
    flagged_df    = comp[comp['flagged'] == True].dropna(subset=['dhan_close']).copy()
    flagged_df['clean'] = flagged_df['ratio'].apply(is_clean_ratio)

    ratio_isins   = set(flagged_df[flagged_df['clean']]['isin'])
    refetch_isins = set(flagged_df[~flagged_df['clean']]['isin'])

    print(f"Classification:")
    print(f"  Safe-append    : {len(safe_isins)}")
    print(f"  Ratio-adjust   : {len(ratio_isins)}")
    print(f"  Full-refetch   : {len(refetch_isins)}")
    print(f"  No-data (skip) : {len(no_data_isins)}")

    if refetch_isins:
        print(f"\n  Full-refetch ISINs (odd ratio):")
        odd = flagged_df[~flagged_df['clean']][['isin','stored_close','dhan_close','ratio','pct_diff']]
        print(odd.to_string(index=False))

    # ── Security ID map ───────────────────────────────────────────────────────
    stats    = pd.read_parquet(REPO_ROOT / "database/stock_statistics.parquet")
    isin_map = build_security_map(stats)

    def make_jobs(isins, from_date, to_date):
        jobs, skipped = [], 0
        for isin in isins:
            if isin in isin_map:
                sid, seg, exch = isin_map[isin]
                jobs.append((isin, sid, seg, exch, from_date, to_date))
            else:
                skipped += 1
        if skipped:
            print(f"  Skipped {skipped} ISINs with no security ID.")
        return jobs

    # ── Load existing price data ──────────────────────────────────────────────
    print(f"\nLoading price_data.parquet...")
    existing = pd.read_parquet(PRICE_PATH)
    existing['date'] = pd.to_datetime(existing['date'])
    print(f"  {len(existing):,} rows, up to {existing['date'].max().date()}")

    session = make_session()

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 1: Safe-append — incremental only
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"PHASE 1: Incremental append — {len(safe_isins)} safe stocks")
    print(f"  Range: {INCREMENTAL_FROM} to {INCREMENTAL_TO}")

    safe_jobs = make_jobs(safe_isins, INCREMENTAL_FROM, INCREMENTAL_TO)
    safe_rows = parallel_fetch(session, safe_jobs, "safe", workers=40)
    print(f"  Fetched {len(safe_rows)} rows.")

    if safe_rows:
        safe_df = pd.DataFrame(safe_rows)
        safe_df['date'] = pd.to_datetime(safe_df['date'])
        for col in ['open','high','low','close','volume']:
            safe_df[col] = pd.to_numeric(safe_df[col], errors='coerce')

        # Only keep rows strictly after existing last date for each ISIN
        existing_last = existing.groupby('isin')['date'].max()
        def keep_new(grp):
            isin = grp.name  # groupby key is available via .name
            cutoff = existing_last.get(isin, pd.Timestamp('1900-01-01'))
            return grp[grp['date'] > cutoff]
        safe_df = safe_df.groupby('isin', group_keys=False).apply(keep_new)
        print(f"  After cutoff filter: {len(safe_df)} truly new rows.")
    else:
        safe_df = pd.DataFrame()

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 2: Ratio-adjust — apply multiplier then fetch incremental
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"PHASE 2: Ratio-adjust — {len(ratio_isins)} corporate-action stocks")

    ratio_lookup = flagged_df[flagged_df['clean']].set_index('isin')['ratio'].to_dict()

    # Adjust stored history for these ISINs
    ratio_existing = existing[existing['isin'].isin(ratio_isins)].copy()
    for isin, grp_idx in ratio_existing.groupby('isin').groups.items():
        r = ratio_lookup.get(isin, 1.0)
        ratio_existing.loc[grp_idx, 'open']  = ratio_existing.loc[grp_idx, 'open']  * r
        ratio_existing.loc[grp_idx, 'high']  = ratio_existing.loc[grp_idx, 'high']  * r
        ratio_existing.loc[grp_idx, 'low']   = ratio_existing.loc[grp_idx, 'low']   * r
        ratio_existing.loc[grp_idx, 'close'] = ratio_existing.loc[grp_idx, 'close'] * r
    print(f"  Applied ratio to {len(ratio_existing):,} stored rows.")

    # Fetch incremental for these ISINs
    ratio_jobs = make_jobs(ratio_isins, INCREMENTAL_FROM, INCREMENTAL_TO)
    ratio_new_rows = parallel_fetch(session, ratio_jobs, "ratio-incr", workers=30)
    print(f"  Fetched {len(ratio_new_rows)} incremental rows.")

    if ratio_new_rows:
        ratio_new_df = pd.DataFrame(ratio_new_rows)
        ratio_new_df['date'] = pd.to_datetime(ratio_new_df['date'])
        for col in ['open','high','low','close','volume']:
            ratio_new_df[col] = pd.to_numeric(ratio_new_df[col], errors='coerce')
    else:
        ratio_new_df = pd.DataFrame()

    # ════════════════════════════════════════════════════════════════════════
    # PHASE 3: Full refetch — odd-ratio stocks
    # ════════════════════════════════════════════════════════════════════════
    if refetch_isins:
        print(f"\n{'='*60}")
        print(f"PHASE 3: Full re-fetch — {len(refetch_isins)} odd-ratio stocks")
        print(f"  Range: {FULL_FROM} to {FULL_TO}")

        refetch_jobs = make_jobs(refetch_isins, FULL_FROM, FULL_TO)
        refetch_rows = parallel_fetch(session, refetch_jobs, "refetch", workers=20)
        print(f"  Fetched {len(refetch_rows)} rows.")

        if refetch_rows:
            refetch_df = pd.DataFrame(refetch_rows)
            refetch_df['date'] = pd.to_datetime(refetch_df['date'])
            for col in ['open','high','low','close','volume']:
                refetch_df[col] = pd.to_numeric(refetch_df[col], errors='coerce')
        else:
            refetch_df = pd.DataFrame()
    else:
        print(f"\nPHASE 3: No odd-ratio stocks — skipping.")
        refetch_df = pd.DataFrame()

    # ════════════════════════════════════════════════════════════════════════
    # MERGE & SAVE
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("Assembling final parquet...")

    # Base: existing rows NOT in any flagged category (safe stocks untouched)
    base = existing[~existing['isin'].isin(ratio_isins | refetch_isins)].copy()
    print(f"  Base (safe + no-data existing rows): {len(base):,}")

    parts = [base]

    # Ratio-adjusted stored history
    if not ratio_existing.empty:
        parts.append(ratio_existing)
        print(f"  Ratio-adjusted history:             {len(ratio_existing):,}")

    # New incremental rows (safe stocks)
    if not safe_df.empty:
        parts.append(safe_df)
        print(f"  New safe-append rows:               {len(safe_df):,}")

    # New incremental rows (ratio-adjusted stocks)
    if not ratio_new_df.empty:
        parts.append(ratio_new_df)
        print(f"  New ratio-stock rows:               {len(ratio_new_df):,}")

    # Full refetch rows (odd-ratio stocks)
    if not refetch_df.empty:
        parts.append(refetch_df)
        print(f"  Full-refetch rows:                  {len(refetch_df):,}")

    combined = pd.concat(parts, ignore_index=True)
    combined = combined.drop_duplicates(subset=['isin', 'date'], keep='last')
    combined = combined.sort_values(['isin', 'date']).reset_index(drop=True)

    print(f"\n  Final rows   : {len(combined):,}")
    print(f"  Unique stocks: {combined['isin'].nunique()}")
    print(f"  Date range   : {combined['date'].min().date()} to {combined['date'].max().date()}")

    # Last-date distribution
    last_by_exch = combined.groupby('exchange')['date'].max()
    print(f"\n  Last date by exchange:")
    for exch, dt in last_by_exch.items():
        print(f"    {exch}: {dt.date()}")

    # Sanity: sample a few ratio stocks
    if ratio_isins:
        sample = list(ratio_isins)[:3]
        sample_summary = (combined[combined['isin'].isin(sample)]
                          .groupby('isin')
                          .agg(start=('date','min'), end=('date','max'), rows=('date','count')))
        print(f"\n  Sample ratio-adjusted stocks:")
        print(sample_summary.to_string())

    combined.to_parquet(PRICE_PATH, index=False)
    print(f"\nSaved -> {PRICE_PATH}")


if __name__ == "__main__":
    main()
