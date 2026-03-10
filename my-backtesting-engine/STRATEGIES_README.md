# Backtesting Strategies

This directory contains multiple trading strategies for backtesting on Indian stock market data.

## Available Strategies

### 1. Technical Strategies

#### Moving Average Crossover (`technical/moving_average_crossover.py`)
Classic trend-following strategy using moving average crossovers.

**Logic:**
- Buy when fast MA crosses above slow MA
- Sell when fast MA crosses below slow MA
- Supports both SMA and EMA

**Parameters:**
- `fast_period`: Fast MA period (default: 20)
- `slow_period`: Slow MA period (default: 50)
- `ma_type`: 'SMA' or 'EMA' (default: 'SMA')

**Use Case:** Trending markets, medium to long-term trades

---

#### RSI Mean Reversion (`technical/rsi_mean_reversion.py`)
Buys oversold stocks and sells overbought stocks using RSI.

**Logic:**
- Buy when RSI < oversold_level (default: 30)
- Sell when RSI > overbought_level (default: 70)
- Assumes mean reversion behavior

**Parameters:**
- `rsi_period`: RSI calculation period (default: 14)
- `oversold_level`: RSI buy trigger (default: 30)
- `overbought_level`: RSI sell trigger (default: 70)

**Use Case:** Range-bound markets, short to medium-term trades

---

### 2. Fundamental Strategies

#### Promoter Accumulation (`fundamental/promoter_accumulation.py`)
Tracks promoter holding changes and buys when promoters are accumulating.

**Logic:**
- Identifies quarters where promoter holding increased significantly
- Buys stocks where promoters increased stake > threshold
- Holds for fixed period (default: 90 days)
- Based on insider buying signal

**Parameters:**
- `min_increase_pct`: Minimum promoter increase % (default: 1.0)
- `min_promoter_holding`: Minimum promoter % required (default: 40.0)
- `holding_period`: Days to hold (default: 90)

**Use Case:** Long-term investment, quality stocks, insider signal following

---

### 3. Hybrid Strategies

#### Quality Momentum (`hybrid/quality_momentum.py`)
Combines high promoter holding (quality) with price momentum.

**Logic:**
- Filters stocks with promoter holding > threshold (e.g., 50%)
- Buys when price momentum > threshold (e.g., 10% over 60 days)
- Sells when momentum turns negative OR after max holding period
- Captures quality stocks in uptrends

**Parameters:**
- `min_promoter_pct`: Minimum promoter % (default: 50.0)
- `lookback_days`: Momentum period (default: 60)
- `min_momentum_pct`: Minimum momentum % (default: 10.0)
- `max_holding_days`: Maximum holding period (default: 180)

**Use Case:** Quality + momentum factor investing, medium to long-term

---

## Running Backtests

### Quick Start

Run backtests on 10 high-quality stocks with all strategies:

```bash
python run_backtests.py
```

### Custom Parameters

```bash
python run_backtests.py \
    --stocks 50 \
    --min-quality 8.0 \
    --start-date 2020-01-01 \
    --end-date 2025-12-31 \
    --capital 500000 \
    --output results/my_backtest.csv
```

**Parameters:**
- `--stocks`: Number of stocks to test (default: 10)
- `--min-quality`: Minimum quality score 0-10 (default: 7.0)
- `--start-date`: Start date YYYY-MM-DD (default: all data)
- `--end-date`: End date YYYY-MM-DD (default: all data)
- `--capital`: Initial capital (default: 100000)
- `--output`: Output CSV file (default: results/backtest_results.csv)

### Output Files

The script generates two files:
1. **CSV file**: Detailed results for each stock-strategy combination
2. **Summary file**: Aggregated statistics by strategy

---

## Strategy Selection Guide

| Market Condition | Recommended Strategy | Reason |
|-----------------|---------------------|---------|
| Strong Uptrend | MA Crossover, Quality Momentum | Captures trend continuation |
| Range-bound | RSI Mean Reversion | Exploits oversold/overbought |
| Quality Focus | Promoter Accumulation, Quality Momentum | Insider buying, strong fundamentals |
| High Volatility | RSI Mean Reversion | Benefits from swings |
| Low Volatility | MA Crossover | Catches breakouts |

---

## Performance Metrics Explained

All strategies return these metrics:

- **total_return_pct**: Overall percentage return
- **num_trades**: Number of completed trades
- **win_rate**: Percentage of profitable trades
- **avg_return_per_trade**: Average return per trade
- **max_drawdown_pct**: Maximum peak-to-trough decline
- **sharpe_ratio**: Risk-adjusted return measure
- **best_trade_pct**: Best single trade return
- **worst_trade_pct**: Worst single trade return

---

## Adding New Strategies

1. Create new file in `technical/`, `fundamental/`, or `hybrid/`
2. Inherit from `Strategy` base class
3. Implement `generate_signals()` and `backtest()` methods
4. Add to `__init__.py` in the category folder
5. Import in `run_backtests.py`

**Example:**

```python
from ...strategies.base import Strategy

class MyStrategy(Strategy):
    def __init__(self, param1, param2):
        self.param1 = param1
        self.name = f"MyStrategy_{param1}"
    
    def generate_signals(self, data):
        # Generate buy/sell signals
        pass
    
    def backtest(self, data, initial_capital=100000):
        # Run backtest logic
        pass
```

---

## Database Access

All strategies use `DatabaseLoader` for efficient data access:

```python
from src.data.loaders import DatabaseLoader

loader = DatabaseLoader('database')

# Get price data for a stock
price_data = loader.get_price_data_for_stock('INE002A01018')

# Get shareholding data
shp_data = loader.load_shareholding_patterns(isins=['INE002A01018'])

# Get stocks by quality
quality_stocks = loader.get_stocks_by_quality(min_quality=8.0)

# Get stocks by industry
it_stocks = loader.get_stocks_by_industry('IT - Software')
```

---

## Tips for Backtesting

1. **Use sufficient data**: Minimum 2 years recommended
2. **Test on quality stocks**: Use quality_score >= 7.0
3. **Consider transaction costs**: Add slippage/brokerage in production
4. **Avoid overfitting**: Test on out-of-sample data
5. **Combine strategies**: Portfolio of strategies reduces risk
6. **Monitor drawdown**: Max drawdown > 30% may be risky
7. **Check Sharpe ratio**: > 1.0 is good, > 2.0 is excellent

---

## Next Steps

1. **Optimize parameters**: Grid search for best parameters
2. **Portfolio backtesting**: Test multiple stocks simultaneously
3. **Walk-forward analysis**: Rolling window backtests
4. **Add transaction costs**: Realistic slippage and brokerage
5. **Risk management**: Position sizing, stop losses
6. **Live trading**: Connect to broker API for execution

---

## Example Results Structure

```
results/
├── backtest_results.csv          # Detailed results
├── backtest_results_summary.txt  # Strategy summary
├── equity_curves/                # Equity curve plots (future)
└── trade_logs/                   # Individual trade logs (future)
```

---

## Questions?

Check the main database README at `database/README.md` for data structure details.
