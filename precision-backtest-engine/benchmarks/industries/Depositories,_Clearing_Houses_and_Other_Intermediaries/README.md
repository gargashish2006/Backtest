# Depositories, Clearing Houses and Other Intermediaries Industry Benchmark

**Type:** Point-in-Time Equal-Weighted Index  
**Rebalancing:** Quarterly  
**Created:** 2026-02-06

---

## Overview

This benchmark represents the **equal-weighted return** of all stocks classified in the **Depositories, Clearing Houses and Other Intermediaries** industry, rebalanced quarterly using point-in-time constituent membership.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total Periods** | 11 quarters |
| **Date Range** | 2023-03-31 to 2025-09-30 |
| **Total Return** | 180.08% |
| **Annualized Return** | 45.43% |
| **Volatility (Std Dev)** | 18.52% |
| **Sharpe Ratio** | 0.63 |
| **Max Drawdown** | -31.70% |
| **Win Rate** | 72.7% |
| **Avg Constituents** | 3 stocks |

---

## Methodology

### Constituent Selection (Point-in-Time)
At each quarterly rebalancing date:
1. Identify all stocks classified in **Depositories, Clearing Houses and Other Intermediaries**
2. Filter stocks that:
   - Had at least 90 days of trading history
   - Were actively trading (price within 30 days)
   - Existed at that point in time (no look-ahead bias)

### Return Calculation
- **Equal-weighted**: Each constituent has equal weight regardless of market cap
- **Rebalancing**: Quarterly (quarter-end dates)
- **Return Period**: Holding period from one quarter-end to next

### No Survivorship Bias
- Only includes stocks that actually existed at each rebalancing date
- Delisted stocks are included up to their delisting date
- New listings enter after meeting minimum history requirement

---

## Files

- `timeseries.csv` - Quarterly returns and constituent counts
- `statistics.csv` - Summary statistics
- `README.md` - This file

---

## Usage Example

```python
import pandas as pd

# Load benchmark
benchmark = pd.read_csv('timeseries.csv')
benchmark['date'] = pd.to_datetime(benchmark['date'])

# Calculate cumulative returns
benchmark['cumulative'] = (1 + benchmark['return'] / 100).cumprod()

# Plot
benchmark.plot(x='date', y='index_value', title='Depositories, Clearing Houses and Other Intermediaries Industry Index')
```

---

**Note:** This is a research benchmark for backtesting purposes. It does not represent an investable product.
