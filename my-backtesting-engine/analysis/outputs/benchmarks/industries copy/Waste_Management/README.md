# Waste Management Industry Benchmark

**Type:** Point-in-Time Equal-Weighted Index  
**Rebalancing:** Quarterly  
**Created:** 2026-02-06

---

## Overview

This benchmark represents the **equal-weighted return** of all stocks classified in the **Waste Management** industry, rebalanced quarterly using point-in-time constituent membership.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total Periods** | 12 quarters |
| **Date Range** | 2022-12-31 to 2025-09-30 |
| **Total Return** | 43.27% |
| **Annualized Return** | 12.73% |
| **Volatility (Std Dev)** | 21.82% |
| **Sharpe Ratio** | 0.24 |
| **Max Drawdown** | -45.21% |
| **Win Rate** | 58.3% |
| **Avg Constituents** | 6 stocks |

---

## Methodology

### Constituent Selection (Point-in-Time)
At each quarterly rebalancing date:
1. Identify all stocks classified in **Waste Management**
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
benchmark.plot(x='date', y='index_value', title='Waste Management Industry Index')
```

---

**Note:** This is a research benchmark for backtesting purposes. It does not represent an investable product.
