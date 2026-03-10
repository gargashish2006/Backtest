# Analysis & Idea Generation

This folder contains tools and resources for analyzing stock data and generating trading strategy ideas.

---

## 📁 Folder Structure

```
analysis/
├── scripts/              # Python helper scripts
│   ├── data_loader.py    # Load database files
│   ├── indicators.py     # Technical indicators
│   ├── screeners.py      # Stock screening functions
│   └── visualizations.py # Chart/plot helpers
├── notebooks/            # Jupyter notebooks for exploration
│   └── [.ipynb files]
├── ideas/                # Strategy ideas & research
│   ├── strategy_ideas.md
│   └── research_questions.md
└── outputs/              # Generated outputs
    ├── charts/           # Saved charts
    ├── reports/          # Analysis reports
    └── screened_stocks/  # Stock screening results
```

---

## 🎯 Purpose

This folder is for **exploratory analysis and idea generation**, separate from backtesting:

1. **Explore Data** - Understand patterns in price, volume, shareholding data
2. **Generate Ideas** - Document strategy hypotheses before implementing
3. **Screen Stocks** - Find stocks meeting specific criteria
4. **Visualize** - Create charts to understand behavior
5. **Research** - Test hypothesis and answer questions
6. **Document** - Track what works and what doesn't

**Workflow:**
```
Explore → Hypothesize → Document → Test → Implement → Backtest
   ↓          ↓            ↓         ↓        ↓          ↓
notebooks   ideas/    strategy   analysis  strategies  results/
           files     _ideas.md             folder      folder
```

---

## 🚀 Quick Start

### 1. Load Data

```python
from analysis.scripts.data_loader import DataLoader

# Initialize loader
loader = DataLoader(database_path="../database")

# Get stock info
stock_info = loader.get_stock_info('INE002A01018')
print(stock_info)

# Get price data
prices = loader.get_stock_prices('INE002A01018')
print(prices.head())

# Search stocks
reliance = loader.search_stocks('reliance')
print(reliance)
```

### 2. Calculate Indicators

```python
from analysis.scripts.indicators import TechnicalIndicators

# Calculate SMA
sma_20 = TechnicalIndicators.sma(prices['close'], 20)

# Calculate RSI
rsi = TechnicalIndicators.rsi(prices['close'], 14)

# Add all indicators at once
prices_with_indicators = TechnicalIndicators.add_all_indicators(prices)
```

### 3. Screen Stocks

```python
from analysis.scripts.screeners import StockScreener

# Initialize screener
screener = StockScreener(loader)

# Screen by RSI
oversold = screener.screen_by_rsi(min_rsi=None, max_rsi=30)
print(f"Found {len(oversold)} oversold stocks")

# Screen by momentum
momentum = screener.screen_by_momentum(min_return_pct=20, period_days=90)
print(momentum.head())

# Screen by MA crossover
crossovers = screener.screen_by_ma_crossover(fast_period=20, slow_period=50)
print(f"Found {len(crossovers)} recent crossovers")

# Multi-criteria screen
criteria = {
    'min_price': 100,
    'max_price': 1000,
    'min_rsi': 40,
    'max_rsi': 60,
    'min_momentum_90d': 10
}
screened = screener.multi_criteria_screen(criteria)
```

### 4. Visualize

```python
from analysis.scripts.visualizations import ChartHelper

# Initialize chart helper
charts = ChartHelper(output_dir="../analysis/outputs/charts")

# Plot price history
charts.plot_price_history(prices, title="Reliance - Price History", 
                          save_as="reliance_price.png")

# Plot with indicators
charts.plot_with_indicators(prices_with_indicators, 
                           indicators=['sma_20', 'sma_50'],
                           title="Reliance with MAs",
                           save_as="reliance_mas.png")

# Plot RSI
charts.plot_rsi(prices_with_indicators, title="Reliance RSI")

# Plot MACD
charts.plot_macd(prices_with_indicators, title="Reliance MACD")
```

---

## 📓 Using Jupyter Notebooks

### Create New Notebook

```bash
cd analysis/notebooks
jupyter notebook
```

### Recommended Notebooks

1. **01_data_exploration.ipynb** - Explore database
   - Load and inspect data
   - Check data quality
   - Understand distributions

2. **02_shareholding_analysis.ipynb** - Analyze promoter holdings
   - Promoter holding changes
   - Correlation with returns
   - Screen by promoter accumulation

3. **03_price_patterns.ipynb** - Find price patterns
   - Breakouts, reversals
   - Volume analysis
   - Momentum studies

4. **04_sector_analysis.ipynb** - Sector performance
   - Sector returns
   - Sector rotation
   - Relative strength

5. **05_strategy_testing.ipynb** - Quick strategy tests
   - Test ideas quickly
   - Validate assumptions
   - Generate signals

---

## 💡 Analysis Examples

### Example 1: Find Stocks with Promoter Accumulation

```python
# Load data
loader = DataLoader()
shareholding = loader.shareholding_df

# Calculate promoter change
# [Your analysis code here]

# Save results
results.to_csv('../outputs/screened_stocks/promoter_accumulation.csv')
```

### Example 2: Test RSI Mean Reversion

```python
# Get all stocks
stocks = loader.master_df['isin'].tolist()

results = []
for isin in stocks[:100]:  # Test on first 100
    prices = loader.get_stock_prices(isin)
    if len(prices) < 100:
        continue
    
    # Calculate RSI
    rsi = TechnicalIndicators.rsi(prices['close'], 14)
    
    # Find oversold instances
    oversold = rsi < 30
    
    # Calculate forward returns
    # [Your analysis code here]
    
    results.append({...})

# Analyze results
results_df = pd.DataFrame(results)
print(results_df.describe())
```

### Example 3: Sector Relative Strength

```python
# Get all industries
industries = loader.get_all_industries()

sector_returns = []
for industry in industries:
    # Get stocks in industry
    stocks = loader.get_stocks_by_industry(industry)
    
    # Calculate average return
    # [Your analysis code here]
    
    sector_returns.append({...})

# Plot sector performance
sector_df = pd.DataFrame(sector_returns)
sector_df.plot(kind='bar')
```

---

## 📝 Documentation Workflow

### 1. Start with Research Question

Document in `ideas/research_questions.md`:
- What are you trying to find out?
- Why does it matter?
- What data do you need?

### 2. Do Analysis

Create notebook in `notebooks/`:
- Load data
- Run analysis
- Create visualizations
- Document findings

### 3. Generate Strategy Idea

If promising, document in `ideas/strategy_ideas.md`:
- Core hypothesis
- Entry/exit conditions
- Parameters
- Expected behavior

### 4. Implement Strategy

Move to main codebase:
- Create strategy class in `src/strategies/`
- Implement `generate_signals()` method
- Follow existing strategy patterns

### 5. Backtest

Use portfolio system:
```bash
python run_portfolio_backtest.py multi \
    --universe top100 \
    --strategy your_strategy \
    --max-positions 20
```

### 6. Review & Iterate

Analyze backtest results:
- Compare to expectations
- Check tax/cost impact
- Refine parameters
- Document learnings

---

## 🛠️ Helper Scripts

### data_loader.py

**Key Functions:**
- `get_stock_info(isin)` - Get stock details
- `get_stock_prices(isin, start, end)` - Get price data
- `get_stock_shareholding(isin)` - Get shareholding data
- `search_stocks(query)` - Search by name/symbol
- `get_stocks_by_industry(industry)` - Filter by industry
- `get_top_stocks_by_data_availability(n)` - Get stocks with most data

### indicators.py

**Available Indicators:**
- Moving Averages: `sma()`, `ema()`
- Oscillators: `rsi()`, `stochastic()`
- Trend: `macd()`, `adx()`
- Volatility: `bollinger_bands()`, `atr()`
- Volume: `obv()`, `vwap()`
- Others: `momentum()`, `volatility()`, `returns()`

### screeners.py

**Screening Functions:**
- `screen_by_price_range()` - Filter by price
- `screen_by_momentum()` - High momentum stocks
- `screen_by_rsi()` - Oversold/overbought
- `screen_by_ma_crossover()` - Recent crossovers
- `screen_by_breakout()` - Price breakouts
- `screen_by_volatility()` - High/low volatility
- `multi_criteria_screen()` - Combine multiple criteria

### visualizations.py

**Chart Types:**
- `plot_price_history()` - Price and volume
- `plot_with_indicators()` - Price with indicators
- `plot_rsi()` - RSI with levels
- `plot_macd()` - MACD histogram
- `plot_bollinger_bands()` - BB with price
- `plot_equity_curve()` - Backtest results
- `plot_comparison()` - Compare multiple stocks

---

## 📊 Output Organization

### charts/
Save all generated charts here:
- Use descriptive names: `reliance_rsi_analysis.png`
- Include date: `sector_performance_2026_02.png`
- Organize by analysis type if needed

### reports/
Save analysis reports:
- Text reports
- Summary CSVs
- Excel workbooks with multiple sheets

### screened_stocks/
Save screening results:
- `oversold_stocks_2026_02_01.csv`
- `momentum_leaders_q1_2026.csv`
- `promoter_accumulation.csv`

---

## 💡 Tips & Best Practices

### Data Analysis
1. Always check data quality first
2. Handle missing values appropriately
3. Consider survivorship bias
4. Use adequate sample size
5. Account for market conditions

### Strategy Development
1. Start simple, add complexity gradually
2. Document assumptions
3. Test on out-of-sample data
4. Consider transaction costs early
5. Understand why it should work

### Visualization
1. Save important charts
2. Use clear titles and labels
3. Include date ranges
4. Add annotations for key events
5. Choose appropriate chart types

### Documentation
1. Write down ideas immediately
2. Document negative results too
3. Link analyses to strategy ideas
4. Review and update regularly
5. Share learnings with team

---

## 🔗 Related Resources

- **Database README**: `../database/README.md`
- **Strategy Guide**: `../STRATEGIES_README.md`
- **Portfolio System**: `../PORTFOLIO_SYSTEM_GUIDE.md`
- **Backtest Results**: `../results/`

---

## 📚 Additional Notes

### When to Use Analysis vs Backtest

**Use Analysis When:**
- Exploring new ideas
- Understanding data patterns
- Generating hypotheses
- Quick what-if tests
- Visualizing concepts

**Use Backtest When:**
- Testing complete strategy
- Measuring realistic returns
- Comparing strategies
- Understanding tax/cost impact
- Production-ready evaluation

### Collaboration

This folder is designed for:
- Individual exploration
- Team knowledge sharing
- Hypothesis documentation
- Research tracking
- Idea generation

---

**Happy Analyzing!** 🚀

Remember: Not every idea will work. Document what doesn't work just as carefully as what does!
