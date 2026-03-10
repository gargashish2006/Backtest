# Dhan daily OHLCV downloader (combined Parquet)

This project includes a Dhan **daily candles** downloader that writes **one combined Parquet file** containing OHLCV for many instruments.

It supports:
- Exchanges: **NSE** and **BSE** (via `exchange_segment` values)
- Instruments: **EQUITY** and **INDEX** (via `instrument`)

## ✅ Requirements

### Environment variables

Set these in your shell before running:

- `DHAN_CLIENT_ID`
- `DHAN_ACCESS_TOKEN`

Optional:
- `DHAN_BASE_URL` (defaults to `https://api.dhan.co`)

### Instruments mapping file

Create a CSV or Parquet file that lists all instruments you want to download.

Required columns:
- `symbol` – your canonical symbol name (e.g. `RELIANCE`, `NIFTY50`)
- `security_id` – Dhan `securityId`
- `exchange_segment` – Dhan `exchangeSegment` (examples below)
- `instrument` – Dhan `instrument` (typically `EQUITY` or `INDEX`)

Optional columns:
- `expiry_code` – defaults to 0 (spot). Needed mainly for derivatives.

Example `dhan_instruments.csv`:

```csv
symbol,security_id,exchange_segment,instrument,expiry_code
RELIANCE,2885,NSE_EQ,EQUITY,0
TCS,11536,NSE_EQ,EQUITY,0
NIFTY50,99999,NSE_IDX,INDEX,0
SENSEX,88888,BSE_IDX,INDEX,0
```

> Dhan `exchangeSegment` values depend on their spec. Common patterns are like `NSE_EQ`, `BSE_EQ`, `NSE_IDX`, `BSE_IDX`.

## 📦 Output schema (Parquet)

One row per `(date, symbol, exchange_segment, instrument)`:

- `date` (YYYY-MM-DD)
- `symbol`
- `exchange_segment`
- `instrument`
- `expiry_code`
- `open`, `high`, `low`, `close`, `volume`

## ▶️ Run the downloader

From the project root (`Backtest/my-backtesting-engine`):

```bash
export DHAN_CLIENT_ID="..."
export DHAN_ACCESS_TOKEN="..."

python -m src.data.providers.dhan_download_daily \
  --instruments ./dhan_instruments.csv \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --out ./data/dhan_daily_all.parquet
```

## Endpoint used

The downloader uses:

- `POST https://api.dhan.co/v2/charts/historical`

Request body:

```json
{
  "securityId": "2885",
  "exchangeSegment": "NSE_EQ",
  "instrument": "EQUITY",
  "expiryCode": 0,
  "fromDate": "2024-01-01",
  "toDate": "2024-01-10"
}
```

Response shape (arrays):

```json
{
  "open": [1290.28, 1292.5],
  "high": [1303.43, 1307.5],
  "low": [1286.58, 1286.5],
  "close": [1295.13, 1305.85],
  "volume": [2015270.0, 3724400.0],
  "timestamp": [1704047400.0, 1704133800.0]
}
```

## Notes / next improvements

- Resume/checkpointing: skip symbols already fully present in the output parquet.
- Chunking: if Dhan imposes max date ranges per request, add windowed downloads.
- Corporate actions: adjustments can be layered on top in a normalization step.
