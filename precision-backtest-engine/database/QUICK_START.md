# Quick Start Guide - Database Usage

**5-Minute Guide to Using the Database**

---

## 🎯 Database Overview

**Location:** `database/` folder  
**Stocks:** 4,609 with complete data (price + shareholding)  
**Unique Identifier:** ISIN (International Securities Identification Number)

---

## 📊 5 Files, 5 Purposes

| File | What It Contains | When To Use |
|------|------------------|-------------|
| `master_identifiers.csv` | Stock codes (NSE/BSE/ISIN) | Need to map between identifier systems |
| `shareholding_patterns.csv` | Quarterly ownership data | Analyzing promoter/FII/DII holdings |
| `price_data.csv` | Daily OHLCV data | Backtesting & price analysis |
| `industry_info.csv` | Industry classification | Sector analysis |
| `stock_statistics.csv` | Pre-calculated metrics | Quick filtering & selection |

---

## ⚡ Quick Examples

### Example 1: Load Price Data for Top 100 Quality Stocks

```python
import pandas as pd

# Step 1: Find high-quality stocks
stats = pd.read_csv('database/stock_statistics.csv')
top_stocks = stats.nlargest(100, 'quality_score')

# Step 2: Load their price data
price = pd.read_csv('database/price_data.csv')
price = price[price['isin'].isin(top_stocks['isin'])]

print(f"Loaded {len(price):,} price records for {price['isin'].nunique()} stocks")
```

---

### Example 2: Get All Data for a Specific Stock

```python
import pandas as pd

# Define the stock (using ISIN)
isin = 'INE002A01018'  # Reliance Industries

# Load all data
master = pd.read_csv('database/master_identifiers.csv')
price = pd.read_csv('database/price_data.csv')
shp = pd.read_csv('database/shareholding_patterns.csv')
stats = pd.read_csv('database/stock_statistics.csv')

# Filter for this stock
stock_info = master[master['isin'] == isin]
stock_price = price[price['isin'] == isin]
stock_shp = shp[shp['isin'] == isin]
stock_stats = stats[stats['isin'] == isin]

print(f"Company: {stock_info['company_name'].iloc[0]}")
print(f"NSE Symbol: {stock_info['nse_symbol'].iloc[0]}")
print(f"Price records: {len(stock_price):,}")
print(f"Shareholding records: {len(stock_shp):,}")
```

---

### Example 3: Filter Liquid Stocks for Day Trading

```python
import pandas as pd

# Load statistics
stats = pd.read_csv('database/stock_statistics.csv')

# Filter for liquid stocks
liquid = stats[
    (stats['median_volume'] > 100000) &  # High volume
    (stats['quality_score'] >= 7) &       # Good quality
    (stats['total_price_records'] > 500)  # Decent history
]

print(f"Found {len(liquid)} liquid stocks")

# Get their ISINs and load price data
isins = liquid['isin'].tolist()
price = pd.read_csv('database/price_data.csv')
price = price[price['isin'].isin(isins)]

# Filter for recent data only
price['date'] = pd.to_datetime(price['date'])
price = price[price['date'] >= '2025-01-01']

print(f"Loaded {len(price):,} recent price records")
```

---

### Example 4: Analyze Shareholding Trends

```python
import pandas as pd

# Load shareholding data
shp = pd.read_csv('database/shareholding_patterns.csv')

# If shareholding columns are available (check your data)
# Group by quarter to see market-wide trends
if 'promoter_holding' in shp.columns:
    quarterly_trends = shp.groupby('quarter').agg({
        'promoter_holding': 'mean',
        'fii_holding': 'mean',
        'dii_holding': 'mean'
    })
    print(quarterly_trends)
```

---

### Example 5: Create a Custom Stock Universe

```python
import pandas as pd

# Load statistics and master
stats = pd.read_csv('database/stock_statistics.csv')
master = pd.read_csv('database/master_identifiers.csv')

# Define criteria
my_universe = stats[
    (stats['quality_score'] >= 8) &           # High quality
    (stats['price_history_years'] >= 5) &    # Long history
    (stats['median_volume'] > 50000) &       # Liquid
    (stats['median_price'] > 100)            # Not penny stocks
]

# Merge with master to get symbols
my_universe = my_universe.merge(
    master[['isin', 'nse_symbol', 'bse_code']], 
    on='isin'
)

print(f"Custom universe: {len(my_universe)} stocks")
print("\nTop 10 stocks:")
print(my_universe[['company_name', 'nse_symbol', 'quality_score']].head(10))

# Save for later use
my_universe.to_csv('my_stock_universe.csv', index=False)
```

---

## 🔑 Key Points to Remember

### 1. Always Use ISIN for Joins
```python
# ✅ Correct
merged = price.merge(shp, on='isin')

# ❌ Wrong - symbols can be duplicated across exchanges
merged = price.merge(shp, on='symbol')
```

### 2. Check Data Quality First
```python
# Always filter by quality_score
stats = stats[stats['quality_score'] >= 6]
```

### 3. Price Data is Pre-sorted
```python
# Already sorted by isin, then date
# No need to sort again for time-series operations
price = pd.read_csv('database/price_data.csv')
price.groupby('isin')['close'].pct_change()  # Works correctly
```

### 4. Some Stocks Listed on Multiple Exchanges
```python
# Check master_identifiers.csv
# One stock may have both NSE and BSE listings
# Use primary_exchange and primary_symbol for the data source
```

---

## 🚨 Common Pitfalls

### Pitfall 1: Loading Entire Price File
❌ **Don't do this** (607 MB file):
```python
price = pd.read_csv('database/price_data.csv')  # Loads all 7M records!
```

✅ **Do this instead**:
```python
# Option 1: Load only needed columns
price = pd.read_csv('database/price_data.csv', 
                    usecols=['isin', 'date', 'close', 'volume'])

# Option 2: Filter while reading
import pandas as pd
isins_needed = ['INE002A01018', 'INE001B01026']
price = pd.read_csv('database/price_data.csv')
price = price[price['isin'].isin(isins_needed)]

# Option 3: Use chunks
chunks = pd.read_csv('database/price_data.csv', chunksize=100000)
price = pd.concat([chunk[chunk['isin'].isin(isins_needed)] for chunk in chunks])
```

---

### Pitfall 2: Ignoring Quality Score
❌ **Don't do this**:
```python
# Using all stocks blindly
all_stocks = stats['isin'].tolist()
```

✅ **Do this instead**:
```python
# Filter by quality first
good_stocks = stats[stats['quality_score'] >= 6]['isin'].tolist()
```

---

### Pitfall 3: Not Checking Data Availability
❌ **Don't assume**:
```python
# Assuming all stocks have 10 years of data
```

✅ **Check first**:
```python
stats = pd.read_csv('database/stock_statistics.csv')
print(f"Avg history: {stats['price_history_years'].mean():.1f} years")
print(f"Min records: {stats['total_price_records'].min()}")

# Filter stocks with sufficient history
sufficient_data = stats[stats['total_price_records'] >= 1000]
```

---

## 📚 File Loading Best Practices

### Efficient Loading Strategy

```python
import pandas as pd

# 1. Always load statistics first (smallest file)
stats = pd.read_csv('database/stock_statistics.csv')

# 2. Filter to get ISINs you need
my_isins = stats[
    (stats['quality_score'] >= 8) & 
    (stats['median_volume'] > 50000)
]['isin'].tolist()

print(f"Selected {len(my_isins)} stocks")

# 3. Load other files filtered by these ISINs
master = pd.read_csv('database/master_identifiers.csv')
master = master[master['isin'].isin(my_isins)]

price = pd.read_csv('database/price_data.csv')
price = price[price['isin'].isin(my_isins)]

shp = pd.read_csv('database/shareholding_patterns.csv')
shp = shp[shp['isin'].isin(my_isins)]

print(f"Loaded {len(price):,} price records")
```

---

## 🎓 Learning Path

1. **Start here:** Load `stock_statistics.csv` and explore the quality_score
2. **Next:** Pick a few high-quality stocks and load their price data
3. **Then:** Try joining price with shareholding data
4. **Finally:** Build a complete backtest with filtered universe

---

## 📞 Need More Help?

- **Detailed Guide:** See `database/README.md`
- **Data Quality:** See `DATA_QUALITY_REPORT.md` in parent directory
- **Complete Summary:** See `COMPLETE_DATA_SUMMARY.md` in parent directory

---

## ⚡ One-Liner Cheat Sheet

```python
# Load high-quality liquid stocks
import pandas as pd
s = pd.read_csv('database/stock_statistics.csv')
good = s[(s['quality_score']>=8)&(s['median_volume']>50000)]['isin']
p = pd.read_csv('database/price_data.csv')
p = p[p['isin'].isin(good)]
print(f"{len(p):,} records, {p['isin'].nunique()} stocks")
```

---

**Happy Backtesting! ��**
