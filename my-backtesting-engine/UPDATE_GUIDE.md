# Price Data Update Guide

## Overview

This guide explains how to update your price data from Dhan to the latest date and handle corporate actions.

## Current Status

- **Last Update**: February 5, 2026
- **Total Stocks**: 4,774
- **Total Records**: 7.1 million
- **Date Range**: Feb 2016 - Feb 5, 2026

## Quick Update (Recommended)

### Step 1: Set Dhan API Credentials

```bash
export DHAN_CLIENT_ID="your_client_id_here"
export DHAN_ACCESS_TOKEN="your_access_token_here"
```

### Step 2: Run the Update Script

```bash
cd /Users/shubhrakasana/Desktop/oleander/olgo_mobile/repos/Backtest/my-backtesting-engine
./update_to_latest.sh
```

This will:
1. ✅ Download data from Feb 6-9, 2026 (4 days)
2. ✅ Enrich with ISIN and company names
3. ✅ Verify corporate actions at overlap dates
4. ✅ Merge with existing database
5. ✅ Flag any price discrepancies > 1%

## Manual Update (Alternative)

If you prefer to run steps manually:

```bash
# Update from specific date range
python3 scripts/update_price_data.py 2026-02-06 2026-02-09 --workers 10
```

## Corporate Action Handling

### What Gets Checked

The update process automatically:
- Compares prices at the overlap date (Feb 6) between old and new data
- Flags stocks with >1% price difference
- Indicates potential corporate actions (splits, bonuses, dividends)

### If Corporate Actions Are Detected

The script will output warnings like:
```
WARNING: Potential corporate actions or data adjustments detected for X stocks:
  ISIN INE123A01012: New Price=150.00, Old Price=300.00 (Diff=50.00%)
```

This indicates a potential 2:1 split. To handle this:

1. **Review the warnings** - Check if they're corporate actions or data errors
2. **Apply adjustments** (if needed):
   ```bash
   python3 scripts/apply_adjustments.py
   ```
   This will back-adjust historical prices for affected stocks

### Understanding Adjustments

- **Stock Split (e.g., 2:1)**: Old prices are divided by 2
- **Bonus (e.g., 1:1)**: Old prices are divided by 2
- **Data Corrections**: New data may have corrections; keep latest

## Verification

After update, verify the data:

```bash
# Check date range
python3 -c "
import pandas as pd
df = pd.read_parquet('database/price_data.parquet')
print('Date range:', df['date'].min(), 'to', df['date'].max())
print('Records for Feb 2026:', len(df[df['date'] >= '2026-02-01']))
"

# Check specific stocks
python3 -c "
import pandas as pd
df = pd.read_parquet('database/price_data.parquet')
# Check a known stock
stock = df[df['symbol'] == 'RELIANCE'].sort_values('date').tail(10)
print(stock[['date', 'symbol', 'close']])
"
```

## Regular Updates (Future)

To keep data current, run weekly:

```bash
# Set your credentials once in ~/.bashrc or ~/.zshrc
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"

# Run update (will auto-detect last date)
cd my-backtesting-engine
python3 scripts/update_price_data.py $(date -v-7d +%Y-%m-%d) $(date +%Y-%m-%d) --workers 10
```

## Troubleshooting

### "Missing Dhan credentials"
- Set `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN` environment variables

### "429 Too Many Requests"
- Reduce `--workers` parameter (try 5 instead of 10)
- Increase `--sleep` in the download command

### "No new data was downloaded"
- Check if DHAN API is accessible
- Verify credentials are valid
- Check date range (data may already exist)

### Corporate Action Confusion
- If unsure whether to apply adjustments, check:
  - BSE/NSE corporate action announcements
  - Compare prices with external sources (Yahoo Finance, MoneyControl)
  - Plot price chart to see if adjustment makes sense

## Data Quality Notes

1. **Dhan provides adjusted prices** for most corporate actions automatically
2. **Overlap verification** helps catch any discrepancies
3. **ISIN-based deduplication** ensures no duplicate records
4. Both **parquet and CSV** files are updated simultaneously

## Files Updated

- `database/price_data.parquet` - Main database (fastest for backtesting)
- `database/price_data.csv` - CSV copy (for manual inspection)
- `data/temp_new_prices.parquet` - Temporary file (auto-deleted)

## Support

For issues with:
- **Dhan API**: Check [Dhan API documentation](https://api.dhan.co/docs)
- **Data quality**: Review `database/README.md`
- **Backtesting**: See `PORTFOLIO_BACKTEST_QUICK_REF.md`
