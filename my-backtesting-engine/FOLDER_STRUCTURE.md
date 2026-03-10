# My Backtesting Engine - Folder Structure

Complete documentation of the folder structure and contents.

---

## 📁 Root Directory

```
my-backtesting-engine/
├── run_backtests.py                    # Main entry point for running backtests
├── run_ma_cross_dual.py                # Legacy MA crossover script
├── FOLDER_STRUCTURE.md                 # This file
├── SETUP_COMPLETE.md                   # Complete setup guide with examples
├── STRATEGIES_README.md                # Strategy documentation
├── DATA_QUALITY_REPORT.md              # Data quality analysis report
├── COMPLETE_DATA_SUMMARY.md            # Project summary
├── RETRY_WORKFLOW.md                   # Guide for retrying failed downloads
├── QUICK_REFERENCE.md                  # Quick reference guide
├── README.md                           # Project README
├── pyproject.toml                      # Python project configuration
├── consolidated_shareholding_patterns.csv  # Source shareholding data (13 MB)
├── daily_price_data_combined.csv       # Combined price data (475 MB)
├── shp_stocks.csv                      # Stock list with industry data (423 KB)
├── stocks_with_complete_data.csv       # 4,609 stocks with both price & shareholding
├── stocks_recommended_for_backtesting.csv  # 2,899 quality stocks (score ≥ 7)
├── stocks_missing_dec25_shareholding.csv   # 342 stocks missing Dec-25 data
├── retry_bse_failures.py               # Script to retry failed BSE downloads
├── retry_dhan_price_failures.py        # Script to retry failed price downloads
└── retry_nse_failures.py               # Script to retry failed NSE downloads
```

---

## 📂 database/ (619 MB) - **PRIMARY DATA SOURCE**

The normalized, production-ready database for backtesting.

```
database/
├── master_identifiers.csv       # 0.29 MB - Stock identifier mappings
├── shareholding_patterns.csv    # 10.80 MB - Quarterly ownership data
├── price_data.csv              # 607 MB - Daily OHLCV price data
├── industry_info.csv           # 0.30 MB - Industry classifications
├── stock_statistics.csv        # 0.63 MB - Pre-calculated metrics
├── README.md                   # 12 KB - Comprehensive database documentation
└── QUICK_START.md              # 8 KB - Quick start guide
```

### File Details:

#### `master_identifiers.csv` (4,609 records)
**Purpose:** Central reference for all stock identifiers  
**Columns:**
- `isin` - International Securities Identification Number (Primary Key)
- `company_name` - Company name
- `nse_symbol` - NSE trading symbol
- `bse_code` - BSE trading code
- `primary_exchange` - Primary listing exchange (NSE/BSE)
- `primary_symbol` - Primary trading symbol
- `data_source` - Source of data (NSE/BSE/Both)

**Use:** Look up stock codes, convert between ISIN/NSE/BSE identifiers

---

#### `shareholding_patterns.csv` (143,545 records)
**Purpose:** Quarterly ownership and shareholding data  
**Columns:**
- `isin` - Stock identifier (links to master_identifiers)
- `company_name` - Company name
- `quarter` - Quarter in 'Mon-YYYY' format (e.g., 'Dec-2025')
- `data_source` - Data source (NSE/BSE)
- `total_shareholders` - Number of shareholders
- `total_outstanding_shares` - Total shares outstanding
- `promoter_holding_pct` - Promoter ownership percentage
- `public_holding_pct` - Public ownership percentage
- `fii_holding_pct` - Foreign Institutional Investors percentage
- `dii_holding_pct` - Domestic Institutional Investors percentage

**Coverage:**
- 92.2% have promoter data
- 35.8% have FII data
- 18.4% have DII data
- 100% have shareholder counts
- 90.1% have Dec-2025 quarter data

**Use:** Track ownership changes, insider buying, institutional activity

---

#### `price_data.csv` (7,116,361 records)
**Purpose:** Daily OHLCV price data for backtesting  
**Columns:**
- `isin` - Stock identifier
- `company_name` - Company name
- `symbol` - Trading symbol
- `exchange` - Exchange (NSE/BSE)
- `date` - Trading date
- `open` - Opening price
- `high` - Highest price
- `low` - Lowest price
- `close` - Closing price
- `volume` - Trading volume

**Coverage:**
- 4,494 unique stocks
- Date range: 2016-02-01 to 2026-01-28 (10 years)
- No stocks have data from both exchanges (clean, non-overlapping)
- Pre-sorted by ISIN and date

**Use:** Historical price data for backtesting strategies

---

#### `industry_info.csv` (4,494 records)
**Purpose:** Industry and sector classification  
**Columns:**
- `isin` - Stock identifier
- `company_name` - Company name
- `industry` - Industry classification
- `industry_group` - Industry group classification

**Coverage:** 100% of stocks have industry data

**Use:** Sector-wise analysis, industry filtering, sector rotation strategies

---

#### `stock_statistics.csv` (4,609 records)
**Purpose:** Pre-calculated summary metrics for quick filtering  
**Columns:**
- `isin` - Stock identifier
- `company_name` - Company name
- `nse_symbol` - NSE symbol
- `bse_code` - BSE code
- `primary_exchange` - Primary exchange
- `total_price_records` - Number of price records
- `price_start_date` - First date of price data
- `price_end_date` - Last date of price data
- `price_history_years` - Years of price history
- `avg_volume` - Average trading volume
- `median_volume` - Median trading volume
- `avg_price` - Average price
- `median_price` - Median price
- `quality_score` - Quality score (0-10)

**Quality Score Breakdown:**
- 10.0: 1,071 stocks - Excellent
- 9.0-9.9: 1,264 stocks - Very Good
- 8.0-8.9: 564 stocks - Good
- 7.0-7.9: 483 stocks - Above Average
- < 7.0: 1,227 stocks - Below Average

**Use:** Quick filtering without loading large price_data.csv

---

## 📂 src/ - **SOURCE CODE**

All strategy and data handling code.

```
src/
├── app.py                          # Main application entry point
├── types/                          # Type definitions
│   └── index.py
├── data/                           # Data collection and loading
│   ├── loaders/                    # Database loaders (NEW)
│   │   ├── __init__.py
│   │   └── database_loader.py      # DatabaseLoader class
│   ├── providers/                  # Data providers
│   │   ├── __init__.py
│   │   ├── dhan_provider.py
│   │   ├── dhan_download_daily.py
│   │   └── nse_xbrl_parser.py
│   ├── parsers/                    # Data parsers
│   │   ├── bse_html_shp_parser.py
│   │   └── nse_shp_xbrl_parser.py
│   ├── dhan_price_downloader.py    # Dhan API price downloader
│   └── bse_shareholding_extractor_selenium.py
├── strategies/                     # Trading strategies
│   ├── __init__.py
│   ├── base.py                     # Base Strategy class
│   ├── examples.py                 # Example strategies
│   ├── ma20_50_dual.py            # Legacy MA strategy
│   ├── technical/                  # Technical analysis strategies (NEW)
│   │   ├── __init__.py
│   │   ├── moving_average_crossover.py  # MA crossover strategy
│   │   └── rsi_mean_reversion.py       # RSI mean reversion
│   ├── fundamental/                # Fundamental strategies (NEW)
│   │   ├── __init__.py
│   │   └── promoter_accumulation.py    # Promoter buying strategy
│   └── hybrid/                     # Hybrid strategies (NEW)
│       ├── __init__.py
│       └── quality_momentum.py         # Quality + momentum
├── backtesting/                    # Backtesting engine
│   ├── __init__.py
│   ├── engine.py                   # Backtest engine
│   ├── portfolio.py                # Portfolio management
│   └── metrics.py                  # Performance metrics
└── execution/                      # Trade execution
    ├── broker.py                   # Broker interface
    └── slippage.py                 # Slippage modeling
```

### Key Components:

#### `src/data/loaders/database_loader.py`
**DatabaseLoader Class** - Efficient data access with caching

**Key Methods:**
- `load_master_identifiers()` - Load stock identifiers
- `load_price_data()` - Load price data with filtering
- `load_shareholding_patterns()` - Load shareholding data
- `load_industry_info()` - Load industry data
- `load_stock_statistics()` - Load pre-calculated stats
- `get_stocks_by_quality()` - Filter by quality score
- `get_stocks_by_industry()` - Filter by industry
- `get_price_data_for_stock()` - Get price data for single stock
- `clear_cache()` - Clear memory cache

---

#### `src/strategies/technical/`
**Moving Average Crossover** (`moving_average_crossover.py`)
- Classic trend-following strategy
- Buy: Fast MA crosses above slow MA
- Sell: Fast MA crosses below slow MA
- Supports SMA and EMA

**RSI Mean Reversion** (`rsi_mean_reversion.py`)
- Contrarian strategy
- Buy: RSI < 30 (oversold)
- Sell: RSI > 70 (overbought)

---

#### `src/strategies/fundamental/`
**Promoter Accumulation** (`promoter_accumulation.py`)
- Buy when promoters increase stake
- Tracks quarter-over-quarter changes
- Holds for fixed period (default: 90 days)

---

#### `src/strategies/hybrid/`
**Quality Momentum** (`quality_momentum.py`)
- Combines high promoter holding with price momentum
- Filters: Promoter holding > 50%
- Buy: Price momentum > 10% over 60 days
- Sell: Momentum turns negative

---

## 📂 results/ - **BACKTEST OUTPUTS**

Output directory for backtest results.

```
results/
├── backtest_results.csv            # Detailed results for each stock-strategy
└── backtest_results_summary.txt    # Aggregated strategy statistics
```

**Created by:** `run_backtests.py`

**Contains:**
- Individual stock-strategy performance
- Metrics: Return %, win rate, Sharpe ratio, drawdown
- Trade counts and statistics
- Strategy comparison data

---

## 📂 archive/ - **CLEANED UP FILES**

Historical files moved during cleanup.

```
archive/
├── debug_files/                    # Debug HTML/JSON files
│   ├── bse_debug.html
│   ├── bse_debug_500002.html
│   ├── bse_debug_532454.html
│   ├── nse_comprehensive_test_RELIANCE_1769599794.json
│   └── nse_research_RELIANCE_*.json
├── source_data/                    # Source/intermediate data files
│   ├── bse_shareholding_patterns.csv
│   ├── nse_shareholding_patterns.csv
│   ├── daily_price_data_bse.csv
│   ├── dhan_instruments.csv
│   ├── bse_failures.csv
│   └── nse_failures.csv
└── duplicate_files/                # Duplicate/backup files
    ├── consolidated_shareholding_patterns copy.csv
    └── nse_shareholding_patterns copy.csv
```

**Purpose:** Keep workspace clean while preserving historical files

---

## 📂 docs/ - **DOCUMENTATION**

Additional documentation (if exists).

```
docs/
└── (Additional documentation files)
```

---

## 📂 tests/ - **TEST SUITE**

Unit tests for strategies and data loaders (if exists).

```
tests/
└── (Test files)
```

---

## 📂 scripts/ - **UTILITY SCRIPTS**

Helper scripts for data management (if exists).

```
scripts/
└── (Utility scripts)
```

---

## Key Reference Files (Root)

### Configuration
- `pyproject.toml` - Python project dependencies and configuration

### Documentation
- `SETUP_COMPLETE.md` - Complete setup guide with usage examples
- `STRATEGIES_README.md` - Detailed strategy documentation
- `DATA_QUALITY_REPORT.md` - Data quality analysis
- `COMPLETE_DATA_SUMMARY.md` - Overall project summary
- `RETRY_WORKFLOW.md` - Guide for retrying failed data downloads
- `QUICK_REFERENCE.md` - Quick reference guide

### Data Reference Files
- `stocks_with_complete_data.csv` - 4,609 stocks with both price & shareholding
- `stocks_recommended_for_backtesting.csv` - 2,899 quality stocks (score ≥ 7)
- `stocks_missing_dec25_shareholding.csv` - 342 stocks to update with Dec-25 data
- `consolidated_shareholding_patterns.csv` - Complete shareholding source (13 MB)
- `daily_price_data_combined.csv` - Complete price source (475 MB)
- `shp_stocks.csv` - Stock list with industry classifications

### Utility Scripts
- `retry_bse_failures.py` - Retry failed BSE shareholding downloads
- `retry_nse_failures.py` - Retry failed NSE shareholding downloads
- `retry_dhan_price_failures.py` - Retry failed price data downloads

---

## Data Flow

```
1. RAW DATA SOURCES
   ├── BSE Website → bse_shareholding_patterns.csv
   ├── NSE Website → nse_shareholding_patterns.csv
   └── Dhan API → daily_price_data_bse.csv

2. CONSOLIDATION
   ├── Shareholding → consolidated_shareholding_patterns.csv
   └── Price → daily_price_data_combined.csv

3. NORMALIZATION
   └── database/ (5 normalized CSV files)
       ├── master_identifiers.csv
       ├── shareholding_patterns.csv
       ├── price_data.csv
       ├── industry_info.csv
       └── stock_statistics.csv

4. BACKTESTING
   └── DatabaseLoader → Strategies → Results
```

---

## File Size Summary

| Location | Size | Files | Purpose |
|----------|------|-------|---------|
| `database/` | 619 MB | 5 CSV + 2 docs | Production data |
| Root CSVs | 488 MB | 3 files | Source data |
| `archive/` | ~750 MB | Various | Historical files |
| `src/` | ~500 KB | Python code | Strategies & loaders |
| `results/` | Variable | CSV/TXT | Backtest outputs |

---

## Important Notes

1. **Primary Data Source:** Always use `database/` folder for backtesting
2. **Do Not Modify:** Database CSV files are production data
3. **Archive:** Source files preserved in `archive/` for reference
4. **Results:** Output goes to `results/` directory
5. **Exchange Resolution:** Each stock has data from only ONE exchange (no duplicates)
6. **Quality Filtering:** Use `quality_score >= 7.0` for reliable backtests
7. **Date Range:** Price data spans 2016-02-01 to 2026-01-28 (10 years)

---

## Quick Access Paths

```python
# In your code, access data using:

from src.data.loaders import DatabaseLoader

loader = DatabaseLoader('database')

# Load specific stock
price_data = loader.get_price_data_for_stock('INE002A01018')

# Load by quality
quality_stocks = loader.get_stocks_by_quality(min_quality=7.0)

# Load by industry
it_stocks = loader.get_stocks_by_industry('IT - Software')
```

---

## Next Steps

1. **Read Documentation:**
   - `SETUP_COMPLETE.md` - Usage examples
   - `STRATEGIES_README.md` - Strategy details
   - `database/README.md` - Database structure

2. **Run Backtests:**
   ```bash
   python run_backtests.py --stocks 10
   ```

3. **Add Custom Strategies:**
   - Create new file in `src/strategies/technical/` or `/fundamental/` or `/hybrid/`
   - Inherit from `Strategy` base class
   - Add to `run_backtests.py`

---

*Last Updated: February 1, 2026*  
*Total Database Size: 619 MB*  
*Total Stocks: 4,609*  
*Strategies: 4 (5 variations)*
