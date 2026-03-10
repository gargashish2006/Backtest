# Retry Failed Downloads Workflow

This guide explains how to retry downloading data for instruments that failed in your initial run.

## Overview

Your initial download run processed 2813 instruments but some failed due to:
- Network interruptions (exit code 146)
- DH-905 "no data present" errors for recently-listed stocks
- API timeouts on large date ranges

The retry workflow allows you to:
1. Identify which instruments failed or were skipped
2. Download only the missing data
3. Merge it with your existing Parquet file (deduplicating automatically)

## Prerequisites

- ✅ You have an existing Parquet file: `./data/dhan_daily_full.parquet`
- ✅ You have the original instruments mapping: `./dhan_instruments.csv`
- ✅ Environment variables set: `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN`

## Step 1: Find Missing Symbols

Run the missing symbols finder script to compare your original instruments list against what was successfully downloaded:

```bash
python scripts/find_missing_symbols.py \
  --instruments ./dhan_instruments.csv \
  --parquet ./data/dhan_daily_full.parquet \
  --out ./data/dhan_daily_full.failures.csv
```

**What this does:**
- Compares the instruments in your CSV against symbols in the Parquet
- Outputs a `.failures.csv` file with instruments that have no data
- Prints a summary of missing vs downloaded symbols
- Provides the exact retry command to run next

**Example output:**
```
Loaded 2813 instruments from ./dhan_instruments.csv
Loaded parquet with 450 unique symbols from ./data/dhan_daily_full.parquet

Missing from parquet: 2363 instruments
  NSE_EQ: 1500
  BSE_EQ: 850
  NSE_IDX: 13

Wrote 2363 failures to ./data/dhan_daily_full.failures.csv
```

## Step 2: Retry Failed Downloads

Use the generated failures CSV as the instruments list for a retry run with merge mode:

```bash
python -m src.data.providers.dhan_download_daily \
  --instruments ./data/dhan_daily_full.failures.csv \
  --start 2019-01-01 \
  --end 2026-01-27 \
  --out ./data/dhan_daily_full.parquet \
  --chunk-days 180 \
  --retries 3 \
  --sleep 0.35 \
  --retry-failures
```

**Key flags:**
- `--instruments`: Uses the failures CSV (only missing symbols)
- `--retry-failures`: Downloads to temp file, then merges with existing Parquet
- `--chunk-days 180`: Splits 7-year range into 6-month chunks (avoids API timeouts)
- `--retries 3`: Retries each chunk 3 times with exponential backoff
- `--sleep 0.35`: 350ms delay between symbols (rate limiting)

**What happens:**
1. Downloads data for missing instruments to a temporary file
2. Merges temp file with your existing `dhan_daily_full.parquet`
3. Deduplicates by `(date, symbol, exchange_segment, instrument, expiry_code)`
4. Overwrites the output file with the merged result
5. Creates a new `.failures.csv` for any that still failed

## Step 3: Repeat if Needed

If some instruments still fail (network issues, API errors), repeat steps 1-2:

```bash
# Check if there are still failures
python scripts/find_missing_symbols.py \
  --instruments ./dhan_instruments.csv \
  --parquet ./data/dhan_daily_full.parquet \
  --out ./data/dhan_daily_full.failures.csv

# If failures exist, retry again
python -m src.data.providers.dhan_download_daily \
  --instruments ./data/dhan_daily_full.failures.csv \
  --start 2019-01-01 \
  --end 2026-01-27 \
  --out ./data/dhan_daily_full.parquet \
  --chunk-days 180 \
  --retries 3 \
  --sleep 0.35 \
  --retry-failures
```

## Understanding Failures

The `.failures.csv` file logs all failures with these columns:
- `symbol`, `security_id`, `exchange_segment`, `instrument`, `expiry_code`
- `fromDate`, `toDate` (the date chunk that failed)
- `error_code`: Type of failure
  - `INVALID_SECURITY_ID`: Security ID format invalid (should be digits only)
  - `NO_DATA`: Empty response from API (no data for this date range)
  - `DH-905`: Dhan API error "no data present / incorrect parameters"
  - `HTTP_ERROR`: Network/API errors (retryable)
- `error_message`: Detailed error description

### Non-Fatal Errors

These are logged but don't stop the download:
- **DH-905 "no data present"**: Recently-listed stocks with incomplete history
- **Empty responses**: API returned no data for a specific date window
- **INVALID_SECURITY_ID**: Security ID doesn't match digits-only pattern

### Retryable Errors

These benefit from retrying with `--retry-failures`:
- **HTTP_ERROR**: Network timeouts, connection issues
- **NO_DATA** (partial): Instrument may have data in other date ranges

## Tips

1. **Start small for testing**: Use `--limit 10` to test the retry workflow on first 10 failures
   ```bash
   python -m src.data.providers.dhan_download_daily \
     --instruments ./data/dhan_daily_full.failures.csv \
     --start 2019-01-01 --end 2026-01-27 \
     --out ./data/dhan_daily_full.parquet \
     --chunk-days 180 --retries 3 --sleep 0.35 \
     --retry-failures --limit 10
   ```

2. **Check progress during long runs**: The script prints status for each instrument
   ```
   [1/2363] NSE_EQ EQUITY RELIANCE: 1834 rows
   [2/2363] NSE_EQ EQUITY TCS: 1821 rows
   ```

3. **Interrupt safely**: Press Ctrl+C to stop. Already-downloaded data is saved to the temp file

4. **Adjust chunk size**: If still getting timeouts, reduce `--chunk-days` (e.g., `--chunk-days 90`)

5. **Rate limiting**: Increase `--sleep` if you hit rate limits (e.g., `--sleep 0.5`)

## Validation

After completion, check the final dataset:

```bash
# Count total rows and unique symbols
python -c "
import pandas as pd
df = pd.read_parquet('./data/dhan_daily_full.parquet')
print(f'Total rows: {len(df):,}')
print(f'Unique symbols: {df.symbol.nunique()}')
print(f'Date range: {df.date.min()} to {df.date.max()}')
print(f'\nBy exchange:')
print(df.groupby('exchange_segment').symbol.nunique())
"
```

Expected output for full dataset (~2813 instruments, 7 years):
```
Total rows: ~4,000,000+
Unique symbols: 2813
Date range: 2019-01-01 to 2026-01-27

By exchange:
exchange_segment
BSE_EQ     1500
NSE_EQ     1200
NSE_IDX      50
BSE_IDX      63
```

## Troubleshooting

### "No such file or directory: .failures.csv"
Run Step 1 first to generate the failures list.

### "RuntimeError: No rows downloaded"
All instruments in the failures CSV still have issues. Check:
- `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN` are valid
- Network connectivity
- The `.failures.csv` to see error codes

### Merge fails with "FileNotFoundError"
The `--out` file doesn't exist. Either:
- Remove `--retry-failures` flag (first run)
- Or provide correct path to existing Parquet

### DH-905 errors for valid stocks
Some stocks may genuinely have no data for the requested date range (e.g., listed after 2019). These are non-fatal and logged to failures.

## Advanced Options

### Stop on First Error (Debugging)
```bash
python -m src.data.providers.dhan_download_daily \
  --instruments ./dhan_instruments.csv \
  --start 2019-01-01 --end 2026-01-27 \
  --out ./data/dhan_daily_full.parquet \
  --chunk-days 180 --retries 3 --sleep 0.35 \
  --stop-on-error
```

### Override API Base URL
```bash
python -m src.data.providers.dhan_download_daily \
  --instruments ./dhan_instruments.csv \
  --start 2019-01-01 --end 2026-01-27 \
  --out ./data/dhan_daily_full.parquet \
  --base-url https://api-staging.dhan.co
```

## Summary

The improved downloader now includes:
- ✅ **Date chunking**: Splits large ranges into manageable windows (default 180 days)
- ✅ **Retry logic**: Exponential backoff for transient failures (default 3 attempts)
- ✅ **Non-fatal errors**: DH-905 and empty responses logged but don't stop processing
- ✅ **Merge mode**: `--retry-failures` downloads missing data and merges with existing file
- ✅ **Failures tracking**: All errors logged to `.failures.csv` for investigation
- ✅ **Validation**: Auto-sanitizes security IDs (strips `.0` suffixes)
- ✅ **Progress tracking**: Real-time status updates during download

You can now reliably download and maintain a complete historical dataset even with network issues or API limitations.
