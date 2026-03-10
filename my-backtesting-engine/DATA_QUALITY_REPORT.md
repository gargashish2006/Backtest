# Data Quality Report - Combined Daily Price Data

**Generated:** January 29, 2026  
**File:** `daily_price_data_combined.csv`  
**Source:** NSE & BSE via Dhan API

---

## 📊 Overall Dataset

| Metric | Value |
|--------|-------|
| **Total Records** | 7,318,446 |
| **Unique Stocks** | 4,948 |
| **Exchanges** | 2 (NSE, BSE) |
| **Date Range** | 2016-02-01 to 2026-01-28 |
| **Time Span** | 3,649 days (~10 years) |
| **File Size** | 475.46 MB |

---

## ✅ Data Completeness

| Metric | Value | Status |
|--------|-------|--------|
| **No Missing Values** | 100% | ✓ All columns complete |
| **Valid Records** | 7,318,446 / 7,318,446 | ✓ Perfect |
| **Data Freshness** | 1 day old | ✓ Updated till Jan 28, 2026 |
| **Recent Coverage** | 98.3% | ✓ Stocks with data in last 7 days |
| **Stale Data** | 0.0% | ✓ No stocks >30 days old |

---

## 📈 Data Quality Metrics

| Issue Type | Count | Percentage | Status |
|------------|-------|------------|--------|
| **Zero Prices** | 72 | 0.00% | 🟢 EXCELLENT |
| **Negative Prices** | 0 | 0.00% | 🟢 PERFECT |
| **Invalid OHLC** | 1 | 0.00% | 🟢 EXCELLENT |
| **Zero Volume** | 2 | 0.00% | 🟢 EXCELLENT |

**Summary:** 99.999% of records are valid with proper OHLC relationships and non-zero prices.

---

## 📊 Exchange Coverage

### BSE (Bombay Stock Exchange)
- **Stocks:** 2,564 (51.8% of total)
- **Records:** 3,701,232 (50.6% of total)
- **Avg Records/Stock:** 1,443
- **Success Rate:** 100%

### NSE (National Stock Exchange)
- **Stocks:** 2,384 (48.2% of total)
- **Records:** 3,617,214 (49.4% of total)
- **Avg Records/Stock:** 1,517
- **Success Rate:** 84.7%

**Coverage:** Balanced distribution with no overlapping symbols between exchanges.

---

## 📅 Temporal Distribution

### Records by Year
| Year | Unique Stocks | Total Records |
|------|---------------|---------------|
| 2016 | 2,783 | 465,210 |
| 2017 | 2,957 | 550,002 |
| 2018 | 3,209 | 563,167 |
| 2019 | 3,281 | 558,128 |
| 2020 | 3,336 | 606,223 |
| 2021 | 3,527 | 720,259 |
| 2022 | 3,757 | 805,129 |
| 2023 | 4,071 | 873,064 |
| 2024 | 4,515 | 1,002,129 |
| 2025 | 4,934 | 1,092,124 |
| 2026 | 4,941 | 83,011 |

**Trend:** Steady growth in both stock count and record volume, peaking in 2025.

---

## 💰 Price Quality Analysis

### Volatility Metrics
- **Normal Returns (<50%):** 7,292,475 records (99.64%)
- **Extreme Moves (>50%):** 21,019 records (0.29%)
- **Stocks with Extreme Moves:** 570 unique stocks
- **Median Daily Range:** 4.01%
- **95th Percentile Range:** 11.36%
- **Wide Ranges (>20%):** 58,113 records (0.79%)

**Assessment:** Normal volatility profile with minimal extreme movements. The 0.29% extreme moves are typical for penny stocks and special situations (splits, corporate actions).

---

## 📦 Volume Quality

| Metric | Value |
|--------|-------|
| **Non-Zero Volume** | 7,318,444 records (100.0%) |
| **Mean Volume** | 1,004,591 shares/day |
| **Median Volume** | 16,117 shares/day |
| **Very Low Volume (<100)** | 365,004 records (4.99%) |
| **Liquid Stocks (>10K vol)** | 4,876 stocks (98.5%) |

**Assessment:** Excellent volume coverage. Low median vs mean indicates presence of high-volume large-caps alongside smaller stocks.

---

## 🎯 Data Depth Distribution

| Category | Stock Count | Percentage |
|----------|-------------|------------|
| **>2,500 records** | 12 | 0.2% |
| **2,000-2,500 records** | 1,934 | 39.1% |
| **1,500-2,000 records** | 593 | 12.0% |
| **1,000-1,500 records** | 664 | 13.4% |
| **500-1,000 records** | 729 | 14.7% |
| **100-500 records** | 808 | 16.3% |
| **<100 records** | 208 | 4.2% |

**Top Performers (Most Data):**
1. CPCAP (NSE) - 4,738 records
2. AG VENTURES LIMITED (BSE) - 4,537 records
3. MOTHERSON (NSE) - 4,515 records

**Assessment:** 
- 39.3% of stocks have >2,000 records (8+ years)
- 64.7% have >1,000 records (4+ years)
- Only 4.2% have insufficient data (<100 records)

---

## 🏆 Overall Quality Score

| Dimension | Rating | Score | Assessment |
|-----------|--------|-------|------------|
| **Completeness** | ⭐⭐⭐⭐⭐ | 5/5 | No missing values |
| **Accuracy** | ⭐⭐⭐⭐⭐ | 5/5 | 99.999% valid records |
| **Freshness** | ⭐⭐⭐⭐⭐ | 5/5 | Updated daily |
| **Coverage** | ⭐⭐⭐⭐⭐ | 5/5 | 4,948 stocks |
| **Consistency** | ⭐⭐⭐⭐⭐ | 5/5 | Uniform format |
| **Depth** | ⭐⭐⭐⭐☆ | 4/5 | Avg 5.8 years/stock |

### **Final Score: 29/30 (EXCELLENT)**

---

## ✅ Production Readiness

### ✓ Ready for Backtesting

This dataset is **production-ready** with the following strengths:

✅ **High Data Quality**
- >99.99% valid records
- Minimal anomalies (72 zero prices, 1 OHLC issue)
- Clean price and volume data

✅ **Excellent Coverage**
- 4,948 unique stocks across NSE & BSE
- Balanced exchange representation (48.2% NSE, 51.8% BSE)
- No duplicate symbols

✅ **Good Historical Depth**
- 10 years total range (2016-2026)
- Average 5.8 years per stock
- 39.3% of stocks have 8+ years of data

✅ **Fresh & Current**
- Updated till January 28, 2026 (1 day old)
- 98.3% of stocks have data in last 7 days
- Zero stale data (>30 days)

✅ **Consistent Format**
- Uniform CSV structure
- Standardized columns: symbol, security_id, date, OHLC, volume, exchange
- Ready for pandas/backtesting libraries

---

## ⚠️ Minor Considerations

### Low-Data Stocks (4.2%)
- **208 stocks** have <100 records
- **Recommendation:** Filter these out for long-term strategies
- **Impact:** Minimal - represents only 4.2% of dataset

### High-Volatility Stocks (11.5%)
- **570 stocks** show extreme price movements (>50% daily moves)
- **Likely causes:** Penny stocks, corporate actions, low liquidity
- **Recommendation:** Apply volatility filters or separate analysis
- **Impact:** Localized to specific stocks

### Low-Volume Stocks (4.99%)
- **365,004 records** with <100 daily volume
- **Recommendation:** Apply volume filters for liquid strategies
- **Impact:** Manageable with standard liquidity filters

---

## 📋 Recommended Filters for Backtesting

For robust backtesting results, consider applying:

1. **Minimum Data Points:** Filter stocks with <250 records (1 year)
2. **Volume Filter:** Require minimum avg daily volume (e.g., >10,000 shares)
3. **Volatility Filter:** Exclude stocks with >50% daily moves frequently
4. **Price Filter:** Exclude penny stocks (e.g., price <₹10)
5. **Recency Filter:** Only include stocks with data in last 30 days

### Example Filter Code:
```python
# Load data
df = pd.read_csv('daily_price_data_combined.csv')
df['date'] = pd.to_datetime(df['date'])

# Calculate stock-level metrics
stock_metrics = df.groupby('symbol').agg({
    'date': ['count', 'max'],
    'volume': 'mean',
    'close': 'mean'
})

# Apply filters
valid_stocks = stock_metrics[
    (stock_metrics[('date', 'count')] >= 250) &  # Min 1 year data
    (stock_metrics[('volume', 'mean')] >= 10000) &  # Liquid
    (stock_metrics[('close', 'mean')] >= 10) &  # Not penny stock
    ((pd.Timestamp.now() - stock_metrics[('date', 'max')]).dt.days <= 30)  # Recent
].index

# Filter dataset
filtered_df = df[df['symbol'].isin(valid_stocks)]
```

---

## 🎯 Use Cases

This dataset is suitable for:

✓ **Long-term Backtesting** (10 years of data)  
✓ **Strategy Development** (diverse stock universe)  
✓ **Cross-sectional Analysis** (4,948 stocks)  
✓ **Factor Research** (multiple years, exchanges)  
✓ **Portfolio Optimization** (broad coverage)  
✓ **Risk Analysis** (complete price & volume data)  
✓ **Market Research** (NSE & BSE combined view)

---

## 📊 Data Schema

```
Columns: 9
- symbol        : Stock trading symbol (string)
- security_id   : Dhan internal security ID (integer)
- date          : Trading date (YYYY-MM-DD)
- open          : Opening price (float)
- high          : Highest price (float)
- low           : Lowest price (float)
- close         : Closing price (float)
- volume        : Trading volume (integer)
- exchange      : Exchange identifier (NSE/BSE)
```

---

## 🔄 Next Steps

1. **Map to Shareholding Patterns** - Join with consolidated shareholding data
2. **Add Fundamental Data** - Integrate company fundamentals (P/E, market cap, etc.)
3. **Create Derived Features** - Calculate technical indicators, returns, etc.
4. **Build Strategy Framework** - Implement backtesting engine
5. **Set Up Monitoring** - Daily updates and quality checks

---

**Report Generated by:** Data Quality Analysis Script  
**Date:** January 29, 2026  
**Contact:** Backtesting Engine Team
