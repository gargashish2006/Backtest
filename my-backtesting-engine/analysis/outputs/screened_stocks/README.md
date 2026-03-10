# Screened Stocks Output Folder

Save stock screening results here.

## File Format

CSV files with columns:
- `isin` - Stock identifier
- `company_name` - Company name
- `symbol` - Trading symbol
- `[screening criteria]` - Values that passed screen

## Naming Convention

- `{criteria}_{date}.csv`
- Example: `oversold_rsi_2026_02_01.csv`

## Common Screens

- `oversold_rsi_*.csv` - RSI < 30
- `momentum_leaders_*.csv` - High momentum stocks
- `ma_crossover_*.csv` - Recent MA crossovers
- `breakout_stocks_*.csv` - Price breakouts
- `promoter_accumulation_*.csv` - Promoter buying

## Usage

These files can be used as:
- Input for backtests
- Universe for strategy testing
- Watchlists for manual review
- Historical screening records
