# Complete Data Summary - Stocks with Price & Shareholding Data

**Generated:** January 29, 2026  
**Purpose:** Identify stocks with both price data and shareholding patterns for backtesting

---

## 📊 Executive Summary

### Coverage Achievement
- **Total Shareholding Stocks:** 4,765
- **Successfully Matched:** 4,609 stocks
- **Coverage Rate:** **96.7%** ✅
- **Unmatched:** 156 stocks (3.3%)

### Data Quality
- **High Quality (Score 8-10):** 1,767 stocks (38.3%)
- **Good Quality (Score 6-7):** 1,577 stocks (34.2%)
- **Recommended for Backtesting:** 2,899 stocks (62.9%)

---

## 🎯 Key Metrics

| Metric | Value | Details |
|--------|-------|---------|
| **Matched Stocks** | 4,609 | 96.7% of shareholding universe |
| **NSE Stocks** | 2,031 | 44.1% of matches |
| **BSE Stocks** | 2,578 | 55.9% of matches |
| **Total Price Records** | 7,318,446 | ~1,588 per stock average |
| **Average Data Depth** | 7.7 years | Per stock |
| **Median Data Depth** | 10.0 years | Per stock |
| **Liquid Stocks (>10K vol)** | 2,535 | 55.0% of matches |
| **Very Liquid (>100K vol)** | 1,063 | 23.1% of matches |

---

## 📈 Exchange Distribution

### NSE (National Stock Exchange)
- **Stocks:** 2,031 (44.1%)
- **Match Method:** Direct symbol matching
- **Average Price Records:** 1,647 per stock
- **Average Quality Score:** 7.7/10

### BSE (Bombay Stock Exchange)
- **Stocks:** 2,578 (55.9%)
- **Match Method:** BSE code mapping via Dhan instruments
- **Average Price Records:** 1,581 per stock
- **Average Quality Score:** 6.7/10

---

## ⭐ Quality Tier Breakdown

### 🥇 High Quality (Score 8-10) - **1,767 stocks (38.3%)**
**Characteristics:**
- Both NSE & BSE codes available
- >2,000 price records (8+ years)
- >5 years of historical data
- Liquid (median volume >10K)

**Use Case:** Ideal for long-term strategy backtesting, factor analysis

**Example Stocks:**
- CPCAP (NSE) - 4,738 records, 10 years
- Motherson (NSE) - 4,515 records, 10 years
- Shriram Finance (BSE) - 4,184 records, 10 years

---

### 🥈 Good Quality (Score 6-7) - **1,577 stocks (34.2%)**
**Characteristics:**
- 1,000-2,000 price records (4-8 years)
- 3-5 years of historical data
- Moderate liquidity

**Use Case:** Suitable for medium-term strategies, sector analysis

**Recommendation:** Apply basic filters (volume, price) before use

---

### 🥉 Decent Quality (Score 4-5) - **775 stocks (16.8%)**
**Characteristics:**
- 500-1,000 price records (2-4 years)
- May lack one identifier (NSE or BSE)
- Lower liquidity

**Use Case:** Short-term strategies, specific stock studies

**Recommendation:** Careful filtering required, check data completeness

---

### ⚠️ Low Quality (Score <4) - **490 stocks (10.7%)**
**Characteristics:**
- <500 price records (<2 years)
- Limited historical data
- Low liquidity possible

**Use Case:** Limited backtesting value, recent IPOs

**Recommendation:** Consider excluding from systematic strategies

---

## 🎯 Recommended Stocks for Backtesting

**File:** `stocks_recommended_for_backtesting.csv`

### Selection Criteria
- Quality Score ≥ 6/10
- Price Records ≥ 500 (2+ years)
- Median Volume > 1,000 shares/day

### Result
- **2,899 stocks qualified** (62.9% of matched stocks)
- Balanced across NSE (44%) and BSE (56%)
- Average 8.2 years of price history
- Average quality score: 7.4/10

### Top Performers

#### NSE Top 5
| Company | Symbol | Records | Years | Score |
|---------|--------|---------|-------|-------|
| CP Capital | CPCAP | 4,738 | 10.0 | 10 |
| Motherson | MOTHERSON | 4,515 | 10.0 | 10 |
| Lloyds Engineering | LLOYDSENGG | 4,150 | 9.5 | 10 |
| Viceroy Hotels | VHLTD | 3,924 | 10.0 | 10 |
| Poonawalla Fin | POONAWALLA | 3,833 | 10.0 | 10 |

#### BSE Top 5
| Company | BSE Code | Records | Years | Score |
|---------|----------|---------|-------|-------|
| Shriram Finance | 511218 | 4,184 | 10.0 | 10 |
| Nava | 513023 | 4,080 | 10.0 | 10 |
| PVR Inox | 532689 | 2,486 | 10.0 | 10 |
| Adani Power | 533096 | 2,478 | 10.0 | 10 |
| REC Ltd | 532955 | 2,477 | 10.0 | 10 |

---

## 💾 Price Data Statistics

### Overall Depth
- **Mean Records/Stock:** 1,584
- **Median Records/Stock:** 1,726
- **Min Records:** 2
- **Max Records:** 4,738 (CPCAP)

### Temporal Coverage
- **Mean Years/Stock:** 7.7 years
- **Median Years/Stock:** 10.0 years
- **Date Range:** 2016-02-01 to 2026-01-28

### Record Distribution
| Records Range | Stock Count | Percentage |
|---------------|-------------|------------|
| >2,500 | 12 | 0.3% |
| 2,000-2,500 | 1,776 | 38.5% |
| 1,500-2,000 | 553 | 12.0% |
| 1,000-1,500 | 625 | 13.6% |
| 500-1,000 | 753 | 16.3% |
| <500 | 890 | 19.3% |

---

## 💰 Liquidity Analysis

### Volume Tiers
| Volume Range | Stock Count | Percentage |
|--------------|-------------|------------|
| >1M shares/day | 191 | 4.1% |
| 100K-1M | 872 | 18.9% |
| 10K-100K | 1,472 | 31.9% |
| 1K-10K | 1,073 | 23.3% |
| <1K | 1,001 | 21.7% |

### Liquid Stocks
- **Liquid (>10K):** 2,535 stocks (55.0%)
- **Very Liquid (>100K):** 1,063 stocks (23.1%)
- **Ultra Liquid (>1M):** 191 stocks (4.1%)

---

## 📋 Data Sources & Matching

### Shareholding Data Sources
- **BSE:** 4,365 stocks (94.7%)
- **NSE:** 244 stocks (5.3%)
- **Consolidated:** Deduplicated by ISIN

### Matching Methods
1. **NSE Direct (2,031 stocks):** Exact NSE symbol matching
2. **BSE Code Mapping (2,578 stocks):** BSE code → Dhan instruments → Price symbols

### Match Quality
- **Perfect Matches:** 4,609 (96.7%)
- **Unmatched:** 156 (3.3%)
  - Reasons: Delisted, recent IPOs, data gaps

---

## 📁 Output Files

### 1. `stocks_with_complete_data.csv`
**Content:** All 4,609 matched stocks  
**Columns:**
- `isin` - Unique ISIN identifier
- `company_name` - Company name
- `bse_code` - BSE security code
- `nse_symbol` - NSE trading symbol
- `data_source` - Original data source (BSE/NSE)
- `matched_symbol` - Price data symbol
- `matched_exchange` - Exchange used for price (NSE/BSE)
- `match_method` - Matching methodology
- `price_records` - Number of price data points
- `price_start_date` - First available price date
- `price_end_date` - Last available price date
- `avg_volume` - Average daily volume
- `median_volume` - Median daily volume
- `avg_price` - Average closing price
- `median_price` - Median closing price
- `price_years` - Years of price data
- `quality_score` - Overall quality (0-10)

**Use:** Comprehensive list for analysis

---

### 2. `stocks_recommended_for_backtesting.csv`
**Content:** 2,899 recommended stocks (quality ≥ 6)  
**Columns:** Same as above  
**Filters Applied:**
- Quality score ≥ 6
- Price records ≥ 500
- Median volume > 1,000

**Use:** Pre-filtered list for immediate backtesting

---

## 🔍 Quality Score Components (0-10 scale)

The quality score is calculated based on:

| Component | Points | Criteria |
|-----------|--------|----------|
| NSE Symbol Present | +2 | Has NSE trading symbol |
| BSE Code Present | +1 | Has BSE security code |
| Decent Data | +1 | >500 price records |
| Good Data | +1 | >1,000 price records |
| Great Data | +1 | >2,000 price records |
| 3+ Years History | +1 | Historical depth ≥ 3 years |
| 5+ Years History | +1 | Historical depth ≥ 5 years |
| 8+ Years History | +1 | Historical depth ≥ 8 years |
| Liquid | +1 | Median volume >10K |

**Maximum Score:** 10 points

---

## 🚀 Usage Recommendations

### For Long-Term Strategies (5+ years)
**Recommended:** Quality score ≥ 8  
**Stocks Available:** 1,767  
**Filters:**
```python
df = df[df['quality_score'] >= 8]
df = df[df['price_years'] >= 5]
df = df[df['median_volume'] > 10000]
```

---

### For Medium-Term Strategies (1-5 years)
**Recommended:** Quality score ≥ 6  
**Stocks Available:** 3,344  
**Filters:**
```python
df = df[df['quality_score'] >= 6]
df = df[df['price_records'] >= 250]
df = df[df['median_volume'] > 5000]
```

---

### For Short-Term Strategies (<1 year)
**Recommended:** Quality score ≥ 4, focus on liquidity  
**Stocks Available:** 4,119  
**Filters:**
```python
df = df[df['quality_score'] >= 4]
df = df[df['median_volume'] > 50000]  # Higher liquidity for short-term
df = df[df['avg_price'] > 10]  # Avoid penny stocks
```

---

## ⚠️ Important Considerations

### Data Gaps
- **156 stocks (3.3%)** from shareholding data could not be matched
- Reasons: Delisted stocks, recent IPOs, data availability issues
- Impact: Minimal on backtesting universe

### Low-Quality Stocks
- **490 stocks (10.7%)** have quality score < 4
- May include: Recent listings, penny stocks, illiquid stocks
- Recommendation: Apply filters before using in systematic strategies

### Volume Considerations
- **21.7%** of stocks have median volume < 1K shares/day
- Low volume can lead to: Execution issues, wide spreads, data anomalies
- Recommendation: Set minimum volume thresholds based on strategy

### Survivorship Bias
- Dataset includes currently available stocks
- Delisted/merged companies may not be fully represented
- Recommendation: Be aware when backtesting long-term strategies

---

## 📊 Next Steps

### 1. Strategy Development
Use the recommended stocks list to:
- Develop and test trading strategies
- Conduct factor analysis
- Build portfolio optimization models
- Test risk management approaches

### 2. Data Enrichment
Consider adding:
- Fundamental data (P/E, market cap, financials)
- Corporate actions (splits, dividends, bonuses)
- Sector/industry classifications
- Technical indicators

### 3. Backtesting Framework
Implement:
- Transaction cost models
- Slippage assumptions based on volume
- Position sizing rules
- Risk limits and constraints

### 4. Monitoring & Updates
Set up:
- Daily price data updates
- Quarterly shareholding updates
- Quality score recalculation
- New stock additions

---

## 📞 Support & Documentation

### Related Files
- `DATA_QUALITY_REPORT.md` - Detailed price data quality analysis
- `daily_price_data_combined.csv` - Complete price dataset (7.3M records)
- `consolidated_shareholding_patterns.csv` - Shareholding patterns (149K records)

### Data Sources
- **Price Data:** Dhan API (NSE & BSE)
- **Shareholding:** NSE & BSE websites
- **Instruments Mapping:** Dhan public instruments CSV

---

**Report Version:** 1.0  
**Last Updated:** January 29, 2026  
**Status:** Production Ready ✅
