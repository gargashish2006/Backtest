# Quick Reference: Retry Failed Downloads

## 1️⃣ Find Missing Symbols

```bash
python scripts/find_missing_symbols.py \
  --instruments ./dhan_instruments.csv \
  --parquet ./data/dhan_daily_full.parquet \
  --out ./data/dhan_daily_full.failures.csv
```

## 2️⃣ Retry Failed Downloads (Merge Mode)

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

## 3️⃣ Validate Results

```bash
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

## 4️⃣ Check for Remaining Failures

```bash
# Run step 1 again to see if any still missing
python scripts/find_missing_symbols.py \
  --instruments ./dhan_instruments.csv \
  --parquet ./data/dhan_daily_full.parquet \
  --out ./data/dhan_daily_full.failures.csv

# If failures remain, run step 2 again
```

---

## Testing with Small Sample

```bash
# Test with first 10 failures
python -m src.data.providers.dhan_download_daily \
  --instruments ./data/dhan_daily_full.failures.csv \
  --start 2019-01-01 --end 2026-01-27 \
  --out ./data/dhan_daily_full.parquet \
  --chunk-days 180 --retries 3 --sleep 0.35 \
  --retry-failures --limit 10
```

---

## Environment Variables Required

```bash
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
```

---

## All Available Flags

```
--instruments    Path to CSV/Parquet with instrument mapping (required)
--start          Start date YYYY-MM-DD (required)
--end            End date YYYY-MM-DD (required)
--out            Output Parquet file path (required)
--chunk-days     Days per API request (default: 180)
--retries        Retry attempts per chunk (default: 3)
--sleep          Seconds between symbols (default: 0.25)
--retry-failures Enable merge mode (downloads to temp, merges with existing)
--limit          Process only first N instruments (debugging)
--stop-on-error  Stop immediately on first error (debugging)
--base-url       Override API base URL (optional)
```
