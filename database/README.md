# Database - Stocks with Complete Data

**Created:** January 29, 2026  
**Source:** Combined NSE & BSE data for backtesting engine  
**Total Stocks:** 4,609 (with both price and shareholding data)

---

## 📁 Database Structure

This database contains normalized data for **4,609 stocks** that have both price data and shareholding patterns available. The data is split across 5 files for efficient querying and analysis.

### File Overview

| File | Records | Size | Purpose |
|------|---------|------|---------|
| `master_identifiers.csv` | 4,609 | 0.29 MB | Stock identifiers and codes |
| `shareholding_patterns.csv` | 143,545 | 5.54 MB | Quarterly ownership data |
| `price_data.csv` | 7,116,361 | 607 MB | Daily OHLCV data |
| `industry_info.csv` | 4,494 | 0.24 MB | Industry classification |
| `stock_statistics.csv` | 4,609 | 0.63 MB | Summary statistics |
| **Total** | - | **613.72 MB** | - |

---

## 🔑 Unique Identifiers

All files use **ISIN** as the primary unique identifier. Additionally:
- **Company Name** serves as a human-readable identifier
- Together, `ISIN + Company Name` uniquely identify each stock

### Why ISIN?
- Universal identifier across exchanges
- Stable (doesn't change with symbol changes)
- Unique across NSE and BSE listings
- Standard for cross-referencing data

---

## 📊 File Descriptions

### 1. `master_identifiers.csv`
**Purpose:** Central reference for all stock identifiers and codes

**Columns:**
- `isin` (string) - Unique ISIN identifier
- `company_name` (string) - Official company name
- `nse_symbol` (string) - NSE trading symbol (empty if not listed on NSE)
- `bse_code` (float) - BSE security code (empty if not listed on BSE)
- `primary_exchange` (string) - Primary exchange used for price data (NSE/BSE)
- `primary_symbol` (string) - Symbol used in price data file
- `data_source` (string) - Original data source (BSE/NSE)

**Use Case:**
- Map between different identifier systems
- Check which exchanges a stock is listed on
- Link to external data sources using ISIN

**Example:**
```csv
isin,company_name,nse_symbol,bse_code,primary_exchange,primary_symbol,data_source
INE002A01018,Reliance Industries,RELIANCE,500325.0,NSE,RELIANCE,BSE
```

---

### 2. `shareholding_patterns.csv`
**Purpose:** Quarterly shareholding and ownership data

**Columns:**
- `isin` (string) - Stock identifier (links to master_identifiers)
- `company_name` (string) - Company name
- `quarter` (string) - Quarter in format "Q1 FY2024" or date
- `data_source` (string) - Data source (BSE/NSE)

**Note:** Additional shareholding columns (promoter_holding, fii_holding, etc.) may vary based on source data availability.

**Use Case:**
- Analyze ownership changes over time
- Track promoter holding trends
- Study FII/DII participation
- Identify quarter-to-quarter patterns

**Example:**
```csv
isin,company_name,quarter,data_source
INE002A01018,Reliance Industries,Q3 FY2025,BSE
```

**Sorting:** Records are sorted by `isin` then `quarter` for efficient time-series queries.

---

### 3. `price_data.csv`
**Purpose:** Daily OHLCV price data with ISIN linkage

**Columns:**
- `isin` (string) - Stock identifier (links to master_identifiers)
- `company_name` (string) - Company name
- `symbol` (string) - Trading symbol used
- `exchange` (string) - Exchange (NSE/BSE)
- `date` (date) - Trading date (YYYY-MM-DD)
- `open` (float) - Opening price
- `high` (float) - Day's high price
- `low` (float) - Day's low price
- `close` (float) - Closing price
- `volume` (integer) - Trading volume (shares)

**Use Case:**
- Backtesting trading strategies
- Technical analysis
- Calculate returns and volatility
- Price trend analysis

**Example:**
```csv
isin,company_name,symbol,exchange,date,open,high,low,close,volume
INE002A01018,Reliance Industries,RELIANCE,NSE,2026-01-28,1245.50,1267.80,1240.00,1260.30,5234567
```

**Sorting:** Records are sorted by `isin` then `date` for efficient time-series queries.

**Date Range:** 2016-02-01 to 2026-01-28 (10 years)

---

### 4. `industry_info.csv`
**Purpose:** Industry and sector classification

**Columns:**
- `isin` (string) - Stock identifier (links to master_identifiers)
- `company_name` (string) - Company name
- `industry` (string) - Industry classification
- `industry_group` (string) - Broader industry group

**Note:** Current version has placeholder values ("Not Available") as industry data was not present in source files. This can be enriched with external classification data.

**Use Case:**
- Sector-wise analysis
- Industry comparison
- Sector rotation strategies
- Portfolio diversification

**Example:**
```csv
isin,company_name,industry,industry_group
INE002A01018,Reliance Industries,Oil & Gas,Energy
```

---

### 5. `stock_statistics.csv`
**Purpose:** Pre-calculated summary statistics for quick filtering

**Columns:**
- `isin` (string) - Stock identifier
- `company_name` (string) - Company name
- `nse_symbol` (string) - NSE symbol
- `bse_code` (float) - BSE code
- `primary_exchange` (string) - Primary exchange
- `total_price_records` (integer) - Number of daily price records
- `price_start_date` (date) - First date with price data
- `price_end_date` (date) - Last date with price data
- `price_history_years` (float) - Years of price history
- `avg_volume` (float) - Average daily volume
- `median_volume` (float) - Median daily volume
- `avg_price` (float) - Average closing price
- `median_price` (float) - Median closing price
- `quality_score` (integer) - Data quality score (0-10)

**Use Case:**
- Quick stock filtering
- Identify liquid stocks
- Check data completeness
- Quality-based selection

**Example:**
```csv
isin,company_name,nse_symbol,bse_code,primary_exchange,total_price_records,price_history_years,median_volume,quality_score
INE002A01018,Reliance Industries,RELIANCE,500325.0,NSE,2475,10.0,8756432,10
```

---

## 🔗 Linking Files

### Basic Join Pattern
```python
import pandas as pd

# Load files
master = pd.read_csv('database/master_identifiers.csv')
price = pd.read_csv('database/price_data.csv')
shp = pd.read_csv('database/shareholding_patterns.csv')
stats = pd.read_csv('database/stock_statistics.csv')

# Join price data with identifiers
price_with_codes = price.merge(master, on=['isin', 'company_name'], how='left')

# Join shareholding with price (by ISIN)
combined = price.merge(shp, on=['isin', 'company_name'], how='left')

# Filter using statistics
high_quality = stats[stats['quality_score'] >= 8]
price_high_quality = price[price['isin'].isin(high_quality['isin'])]
```

---

## 📈 Data Coverage

### Stocks
- **Total Stocks:** 4,609
- **Unique ISINs:** 4,494
- **NSE Listed:** 2,031 (44.1%)
- **BSE Listed:** 2,578 (55.9%)

### Price Data
- **Total Records:** 7,116,361
- **Date Range:** 2016-02-01 to 2026-01-28
- **Average Records/Stock:** 1,544
- **Average History:** 7.7 years per stock

### Shareholding Data
- **Total Records:** 143,545
- **Unique Stocks:** 4,494
- **Quarterly Data:** Multiple quarters per stock

---

## 🎯 Common Use Cases

### 1. Find Liquid Stocks with Long History
```python
# Load statistics
stats = pd.read_csv('database/stock_statistics.csv')

# Filter
liquid_stocks = stats[
    (stats['quality_score'] >= 8) &
    (stats['total_price_records'] >= 1000) &
    (stats['median_volume'] > 50000)
]

# Get their ISINs
isins = liquid_stocks['isin'].tolist()

# Load price data for these stocks
price = pd.read_csv('database/price_data.csv')
price_filtered = price[price['isin'].isin(isins)]
```

---

### 2. Analyze Shareholding Changes
```python
# Load shareholding data
shp = pd.read_csv('database/shareholding_patterns.csv')

# Filter for a specific stock
reliance_shp = shp[shp['isin'] == 'INE002A01018']

# If shareholding columns exist, analyze trends
# reliance_shp.plot(x='quarter', y='promoter_holding')
```

---

### 3. Get Complete Stock Profile
```python
def get_stock_profile(isin):
    """Get complete profile for a stock"""
    # Master info
    master = pd.read_csv('database/master_identifiers.csv')
    info = master[master['isin'] == isin].iloc[0]
    
    # Statistics
    stats = pd.read_csv('database/stock_statistics.csv')
    stock_stats = stats[stats['isin'] == isin].iloc[0]
    
    # Price data
    price = pd.read_csv('database/price_data.csv')
    price_data = price[price['isin'] == isin]
    
    # Shareholding
    shp = pd.read_csv('database/shareholding_patterns.csv')
    shp_data = shp[shp['isin'] == isin]
    
    return {
        'info': info,
        'stats': stock_stats,
        'price': price_data,
        'shareholding': shp_data
    }

# Example
profile = get_stock_profile('INE002A01018')
```

---

### 4. Sector-wise Analysis
```python
# Load industry info and stats
industry = pd.read_csv('database/industry_info.csv')
stats = pd.read_csv('database/stock_statistics.csv')

# Merge
stocks_with_industry = stats.merge(industry, on=['isin', 'company_name'])

# Group by sector
sector_stats = stocks_with_industry.groupby('industry').agg({
    'isin': 'count',
    'median_volume': 'mean',
    'quality_score': 'mean'
})
```

---

## 🔄 Data Updates

To keep the database current:

1. **Update Price Data:**
   - Run price downloader for new dates
   - Filter for complete stocks ISINs
   - Append to `price_data.csv`

2. **Update Shareholding:**
   - Download new quarterly data
   - Filter for complete stocks ISINs
   - Append to `shareholding_patterns.csv`

3. **Recalculate Statistics:**
   - Update `stock_statistics.csv` with new metrics
   - Recalculate quality scores

---

## ⚠️ Important Notes

### ISIN Uniqueness
- Some ISINs may have multiple entries in `master_identifiers.csv` if listed on both NSE and BSE
- Use `primary_exchange` and `primary_symbol` to determine which exchange data is used in `price_data.csv`

### Data Quality
- Not all stocks have full 10-year history
- Check `total_price_records` in `stock_statistics.csv` before analysis
- Use `quality_score` for quick filtering

### Industry Data
- Currently contains placeholder values
- Can be enriched with external sources like:
  - NSE/BSE industry classifications
  - Bloomberg/Reuters sector codes
  - Manual classification

### Volume Caveats
- Some stocks have very low volume (<1K daily)
- Check `median_volume` before using for liquid strategies
- Consider filtering out low-volume stocks

---

## 📊 Data Quality Distribution

Based on `quality_score` (0-10):

| Quality Tier | Score | Stock Count | Percentage |
|--------------|-------|-------------|------------|
| High Quality | 8-10 | 1,767 | 38.3% |
| Good Quality | 6-7 | 1,577 | 34.2% |
| Decent | 4-5 | 775 | 16.8% |
| Low | 0-3 | 490 | 10.7% |

**Recommended:** Use stocks with quality_score ≥ 6 for robust backtesting.

---

## 🚀 Getting Started

### Quick Start Example
```python
import pandas as pd

# 1. Load stock statistics to find good candidates
stats = pd.read_csv('database/stock_statistics.csv')
good_stocks = stats[
    (stats['quality_score'] >= 8) &
    (stats['median_volume'] > 10000)
]

print(f"Found {len(good_stocks)} high-quality liquid stocks")

# 2. Load price data for these stocks
price = pd.read_csv('database/price_data.csv')
price = price[price['isin'].isin(good_stocks['isin'])]

print(f"Loaded {len(price):,} price records")

# 3. Calculate returns
price['date'] = pd.to_datetime(price['date'])
price = price.sort_values(['isin', 'date'])
price['returns'] = price.groupby('isin')['close'].pct_change()

# 4. Ready for backtesting!
```

---

## 📞 Support

For questions or issues with this database:
- Check the parent directory for `COMPLETE_DATA_SUMMARY.md`
- Review `DATA_QUALITY_REPORT.md` for quality metrics
- Refer to source files in parent directory

---

**Database Version:** 1.0  
**Last Updated:** January 29, 2026  
**Status:** Production Ready ✅
