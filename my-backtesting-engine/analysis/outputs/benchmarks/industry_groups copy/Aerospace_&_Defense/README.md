# Aerospace & Defense Industry Group Benchmark

**Type:** Point-in-Time Equal-Weighted Index  
**Level:** Industry Group (Aggregated)  
**Rebalancing:** Quarterly  
**Created:** 2026-02-06

---

## Overview

This benchmark represents the **equal-weighted return** of all stocks classified in the **Aerospace & Defense** industry group, rebalanced quarterly using point-in-time constituent membership.

An industry group aggregates multiple related industries. For example, "Financial Services" includes Banks, NBFCs, Insurance, etc.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total Periods** | 38 quarters |
| **Date Range** | 2016-06-30 to 2025-09-30 |
| **Total Return** | 1721.73% |
| **Annualized Return** | 35.73% |
| **Volatility (Std Dev)** | 25.24% |
| **Sharpe Ratio** | 0.42 |
| **Max Drawdown** | -59.55% |
| **Win Rate** | 60.5% |
| **Avg Constituents** | 13 stocks |
| **Avg Industries** | 1 industries |

---

## Composition

This industry group typically contains:
- **1 distinct industries** (on average)
- **13 stocks** (on average)
- Range: 6 to 22 stocks per quarter

---

## Methodology

### Constituent Selection (Point-in-Time)
At each quarterly rebalancing date:
1. Identify all stocks classified in **Aerospace & Defense** industry group
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

- `timeseries.csv` - Quarterly returns, constituent counts, and industry counts
- `statistics.csv` - Summary statistics
- `README.md` - This file

---

## Usage Example

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load benchmark
benchmark = pd.read_csv('timeseries.csv')
benchmark['date'] = pd.to_datetime(benchmark['date'])

# Plot index value
plt.figure(figsize=(12, 6))
plt.plot(benchmark['date'], benchmark['index_value'])
plt.title('Aerospace & Defense Industry Group Index')
plt.ylabel('Index Value (Base 100)')
plt.xlabel('Date')
plt.grid(alpha=0.3)
plt.show()

# Print statistics
print(f"Total Return: {(benchmark['index_value'].iloc[-1] - 100):.2f}%")
print(f"Annualized: {((benchmark['index_value'].iloc[-1] / 100) ** (4 / len(benchmark)) - 1) * 100:.2f}%")
```

---

**Note:** This is a research benchmark for backtesting purposes. It does not represent an investable product.
