# Example Analysis - Getting Started

This file demonstrates how to use the analysis tools.

## Setup

```python
import sys
sys.path.append('..')

import pandas as pd
from scripts.data_loader import DataLoader
from scripts.indicators import TechnicalIndicators
from scripts.screeners import StockScreener
from scripts.visualizations import ChartHelper
```

## Example 1: Load and Explore Data

```python
# Initialize data loader
loader = DataLoader(database_path="../database")

# Get basic stats
print(f"Total stocks: {len(loader.master_df)}")
print(f"Exchanges: {loader.get_stock_count_by_exchange()}")

# Search for a stock
stocks = loader.search_stocks("reliance")
print(stocks[['company_name', 'primary_symbol', 'primary_exchange']])

# Get price data
isin = stocks.iloc[0]['isin']
prices = loader.get_stock_prices(isin)
print(f"Price data: {len(prices)} days")
print(prices.tail())
```

## Example 2: Calculate Technical Indicators

```python
# Calculate indicators
prices['sma_20'] = TechnicalIndicators.sma(prices['close'], 20)
prices['sma_50'] = TechnicalIndicators.sma(prices['close'], 50)
prices['rsi'] = TechnicalIndicators.rsi(prices['close'], 14)

# Or add all at once
prices_full = TechnicalIndicators.add_all_indicators(prices)
print(prices_full.columns)
```

## Example 3: Screen Stocks

```python
# Initialize screener
screener = StockScreener(loader)

# Find oversold stocks
oversold = screener.screen_by_rsi(min_rsi=None, max_rsi=30)
print(f"Oversold stocks (RSI < 30): {len(oversold)}")
print(oversold.head())

# Find momentum leaders
momentum = screener.screen_by_momentum(min_return_pct=20, period_days=90)
print(f"Momentum leaders (>20% in 90d): {len(momentum)}")
print(momentum.head())

# Multi-criteria screen
criteria = {
    'min_price': 100,
    'max_price': 1000,
    'min_rsi': 40,
    'max_rsi': 60
}
screened = screener.multi_criteria_screen(criteria)
print(f"Stocks meeting all criteria: {len(screened)}")
```

## Example 4: Visualize

```python
# Initialize chart helper
charts = ChartHelper(output_dir="../outputs/charts")

# Plot price history
charts.plot_price_history(prices, 
                          title=f"{stocks.iloc[0]['company_name']} - Price History",
                          save_as="example_price.png")

# Plot with moving averages
charts.plot_with_indicators(prices,
                            indicators=['sma_20', 'sma_50'],
                            title="Price with Moving Averages")

# Plot RSI
charts.plot_rsi(prices_full, title="RSI Analysis")
```

## Example 5: Analyze Results

```python
# Calculate returns
prices['returns'] = TechnicalIndicators.returns(prices['close'])

# Summary statistics
summary = loader.get_price_summary(isin)
print(f"\\nSummary for {summary['isin']}:")
print(f"Period: {summary['start_date']} to {summary['end_date']}")
print(f"Total Return: {summary['total_return_pct']:.2f}%")
print(f"Average Price: ₹{summary['avg_close']:.2f}")
```

## Next Steps

1. Create your own Jupyter notebook
2. Explore different stocks and patterns
3. Test strategy hypotheses
4. Document findings in ideas/ folder
5. Implement promising strategies
6. Backtest with portfolio system

---

**Note:** This is a template. Create actual Jupyter notebooks in the notebooks/ folder for interactive analysis.
