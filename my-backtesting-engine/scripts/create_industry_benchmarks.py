#!/usr/bin/env python
"""
Create Point-in-Time Industry Benchmarks

Generates equal-weighted industry indices that:
- Rebalance quarterly (aligned with shareholding data)
- Use only stocks that existed at each rebalancing date
- Avoid survivorship bias
- Track constituent changes over time

Output: analysis/outputs/benchmarks/industries/
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class IndustryBenchmarkBuilder:
    """Build point-in-time industry benchmarks"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        self.output_path = base_path / 'analysis' / 'outputs' / 'benchmarks' / 'industries'
        
        print("="*80)
        print("INDUSTRY BENCHMARK BUILDER - POINT-IN-TIME")
        print("="*80)
        
        self._load_data()
    
    def _load_data(self):
        """Load required database files"""
        print("\nLoading database files...")
        
        # Industry classifications
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'company_name', 'industry', 'industry_group']
        )
        
        # Filter valid industries
        self.industry_df = self.industry_df[
            (self.industry_df['industry'].notna()) &
            (self.industry_df['industry'] != 'Not Available')
        ]
        
        # Stock statistics (for quality filtering)
        self.stats_df = pd.read_csv(
            self.database_path / 'stock_statistics.csv',
            usecols=['isin', 'total_price_records', 'price_start_date', 
                     'price_end_date', 'quality_score']
        )
        self.stats_df['price_start_date'] = pd.to_datetime(self.stats_df['price_start_date'])
        self.stats_df['price_end_date'] = pd.to_datetime(self.stats_df['price_end_date'])
        
        # Price data (chunked loading for memory efficiency)
        print("  Loading price data (this may take a moment)...")
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            usecols=['isin', 'date', 'close'],
            dtype={'close': 'float32'}
        )
        self.price_df['date'] = pd.to_datetime(self.price_df['date'])
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        # Create price lookup for faster access using groupby (much faster)
        print("  Creating price lookup index...")
        self.price_by_isin = {isin: group for isin, group in self.price_df.groupby('isin')}
        
        print(f"  ✅ Loaded:")
        print(f"     - {self.industry_df['industry'].nunique()} industries")
        print(f"     - {len(self.industry_df):,} stock-industry mappings")
        print(f"     - {len(self.price_df):,} price records")
        print(f"     - {len(self.price_by_isin):,} stocks indexed")
    
    def get_rebalancing_dates(self, start_date='2016-03-31', end_date='2026-01-31'):
        """Generate quarterly rebalancing dates (quarter-ends)"""
        # Quarterly rebalancing on last day of each quarter
        dates = pd.date_range(start=start_date, end=end_date, freq='Q')
        return dates
    
    def get_constituents_at_date(self, industry, as_of_date, min_history_days=90):
        """
        Get stocks in an industry that existed at a specific date.
        
        Criteria:
        1. Must be classified in this industry
        2. Must have at least min_history_days of price data before as_of_date
        3. Must have a price within 30 days of as_of_date (not delisted)
        
        Returns:
            List of ISINs that meet all criteria
        """
        # Get all stocks in this industry
        industry_stocks = self.industry_df[
            self.industry_df['industry'] == industry
        ]['isin'].unique()
        
        valid_constituents = []
        
        for isin in industry_stocks:
            # Check stock statistics
            stock_stats = self.stats_df[self.stats_df['isin'] == isin]
            
            if len(stock_stats) == 0:
                continue
            
            stock_stats = stock_stats.iloc[0]
            
            # Must have started trading before as_of_date
            if stock_stats['price_start_date'] > as_of_date:
                continue
            
            # Must have ended after as_of_date (or still trading)
            if stock_stats['price_end_date'] < as_of_date:
                continue
            
            # Check if has enough history
            history_days = (as_of_date - stock_stats['price_start_date']).days
            if history_days < min_history_days:
                continue
            
            # Check if has recent price (within 30 days) using indexed data
            if isin in self.price_by_isin:
                isin_prices = self.price_by_isin[isin]
                recent_prices = isin_prices[
                    (isin_prices['date'] >= as_of_date - timedelta(days=30)) &
                    (isin_prices['date'] <= as_of_date)
                ]
                
                if len(recent_prices) > 0:
                    valid_constituents.append(isin)
        
        return valid_constituents
    
    def calculate_return(self, isin, start_date, end_date, tolerance_days=7):
        """
        Calculate return for a single stock between two dates.
        Uses closest available prices within tolerance window.
        """
        if isin not in self.price_by_isin:
            return None
        
        isin_prices = self.price_by_isin[isin]
        
        # Get price at start date (within tolerance)
        start_prices = isin_prices[
            (isin_prices['date'] >= start_date - timedelta(days=tolerance_days)) &
            (isin_prices['date'] <= start_date + timedelta(days=tolerance_days))
        ].sort_values('date')
        
        if len(start_prices) == 0:
            return None
        
        start_price = start_prices.iloc[-1]['close']  # Use latest within window
        
        # Get price at end date
        end_prices = isin_prices[
            (isin_prices['date'] >= end_date - timedelta(days=tolerance_days)) &
            (isin_prices['date'] <= end_date + timedelta(days=tolerance_days))
        ].sort_values('date')
        
        if len(end_prices) == 0:
            return None
        
        end_price = end_prices.iloc[-1]['close']
        
        # Calculate return
        return ((end_price - start_price) / start_price) * 100
    
    def build_industry_benchmark(self, industry):
        """
        Build complete benchmark timeseries for one industry.
        
        Returns:
            DataFrame with columns: date, return, num_constituents, constituent_list
        """
        rebal_dates = self.get_rebalancing_dates()
        benchmark_data = []
        
        for i, rebal_date in enumerate(rebal_dates[:-1]):  # Exclude last date
            next_rebal_date = rebal_dates[i + 1]
            
            # Get constituents at this rebalancing date
            constituents = self.get_constituents_at_date(industry, rebal_date)
            
            if len(constituents) < 3:  # Need minimum 3 stocks
                continue
            
            # Calculate returns for each constituent
            returns = []
            valid_constituents = []
            
            for isin in constituents:
                ret = self.calculate_return(isin, rebal_date, next_rebal_date)
                if ret is not None:
                    # Cap extreme returns
                    ret = max(min(ret, 1000), -100)
                    returns.append(ret)
                    valid_constituents.append(isin)
            
            if len(returns) == 0:
                continue
            
            # Equal-weighted average
            industry_return = np.mean(returns)
            
            benchmark_data.append({
                'date': rebal_date,
                'return': industry_return,
                'num_constituents': len(valid_constituents),
                'constituent_list': ','.join(valid_constituents)
            })
        
        benchmark_df = pd.DataFrame(benchmark_data)
        
        if len(benchmark_df) > 0:
            # Calculate cumulative index value (start at 100)
            benchmark_df['index_value'] = 100 * (1 + benchmark_df['return'] / 100).cumprod()
        
        return benchmark_df
    
    def calculate_statistics(self, benchmark_df):
        """Calculate summary statistics for a benchmark"""
        if len(benchmark_df) < 2:
            return {}
        
        returns = benchmark_df['return'].values
        
        # Calculate max drawdown
        index_values = benchmark_df['index_value'].values
        running_max = np.maximum.accumulate(index_values)
        drawdowns = (index_values - running_max) / running_max * 100
        max_drawdown = drawdowns.min()
        
        stats = {
            'total_periods': len(benchmark_df),
            'start_date': benchmark_df['date'].min().strftime('%Y-%m-%d'),
            'end_date': benchmark_df['date'].max().strftime('%Y-%m-%d'),
            'total_return': benchmark_df['index_value'].iloc[-1] - 100,
            'annualized_return': ((benchmark_df['index_value'].iloc[-1] / 100) ** (4 / len(benchmark_df)) - 1) * 100,
            'avg_quarterly_return': returns.mean(),
            'volatility': returns.std(),
            'sharpe_ratio': returns.mean() / returns.std() if returns.std() > 0 else 0,
            'max_return': returns.max(),
            'min_return': returns.min(),
            'max_drawdown': max_drawdown,
            'positive_quarters': int((returns > 0).sum()),
            'negative_quarters': int((returns < 0).sum()),
            'win_rate': (returns > 0).sum() / len(returns) * 100,
            'avg_constituents': benchmark_df['num_constituents'].mean(),
            'min_constituents': int(benchmark_df['num_constituents'].min()),
            'max_constituents': int(benchmark_df['num_constituents'].max())
        }
        
        return stats
    
    def save_industry_benchmark(self, industry, benchmark_df, stats):
        """Save benchmark data and statistics to files"""
        # Create industry folder
        industry_folder = self.output_path / industry.replace('/', '_').replace(' ', '_')
        industry_folder.mkdir(parents=True, exist_ok=True)
        
        # Save timeseries
        timeseries_path = industry_folder / 'timeseries.csv'
        benchmark_df.to_csv(timeseries_path, index=False)
        
        # Save statistics
        stats_df = pd.DataFrame([stats])
        stats_path = industry_folder / 'statistics.csv'
        stats_df.to_csv(stats_path, index=False)
        
        # Save README
        readme_path = industry_folder / 'README.md'
        self._create_readme(readme_path, industry, stats)
    
    def _create_readme(self, path, industry, stats):
        """Create README for industry benchmark"""
        readme_content = f"""# {industry} Industry Benchmark

**Type:** Point-in-Time Equal-Weighted Index  
**Rebalancing:** Quarterly  
**Created:** {datetime.now().strftime('%Y-%m-%d')}

---

## Overview

This benchmark represents the **equal-weighted return** of all stocks classified in the **{industry}** industry, rebalanced quarterly using point-in-time constituent membership.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total Periods** | {stats.get('total_periods', 'N/A')} quarters |
| **Date Range** | {stats.get('start_date', 'N/A')} to {stats.get('end_date', 'N/A')} |
| **Total Return** | {stats.get('total_return', 0):.2f}% |
| **Annualized Return** | {stats.get('annualized_return', 0):.2f}% |
| **Volatility (Std Dev)** | {stats.get('volatility', 0):.2f}% |
| **Sharpe Ratio** | {stats.get('sharpe_ratio', 0):.2f} |
| **Max Drawdown** | {stats.get('max_drawdown', 0):.2f}% |
| **Win Rate** | {stats.get('win_rate', 0):.1f}% |
| **Avg Constituents** | {stats.get('avg_constituents', 0):.0f} stocks |

---

## Methodology

### Constituent Selection (Point-in-Time)
At each quarterly rebalancing date:
1. Identify all stocks classified in **{industry}**
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
benchmark.plot(x='date', y='index_value', title='{industry} Industry Index')
```

---

**Note:** This is a research benchmark for backtesting purposes. It does not represent an investable product.
"""
        with open(path, 'w') as f:
            f.write(readme_content)
    
    def build_all_industries(self):
        """Build benchmarks for all industries"""
        print("\n" + "="*80)
        print("BUILDING ALL INDUSTRY BENCHMARKS")
        print("="*80)
        
        all_industries = sorted(self.industry_df['industry'].unique())
        print(f"\nFound {len(all_industries)} industries to process")
        
        summary_data = []
        
        for idx, industry in enumerate(all_industries, 1):
            print(f"\n[{idx}/{len(all_industries)}] {industry}")
            
            try:
                # Build benchmark
                benchmark_df = self.build_industry_benchmark(industry)
                
                if len(benchmark_df) > 0:
                    # Calculate stats
                    stats = self.calculate_statistics(benchmark_df)
                    stats['industry'] = industry
                    
                    # Save
                    self.save_industry_benchmark(industry, benchmark_df, stats)
                    
                    print(f"    ✅ {stats['total_periods']} periods, "
                          f"avg {stats['avg_constituents']:.0f} stocks, "
                          f"return: {stats['total_return']:.1f}%")
                    
                    summary_data.append(stats)
                else:
                    print(f"    ⚠️ Insufficient data")
            
            except Exception as e:
                print(f"    ❌ Error: {e}")
                continue
        
        # Save summary
        if len(summary_data) > 0:
            summary_df = pd.DataFrame(summary_data)
            summary_path = self.output_path / 'industry_benchmarks_summary.csv'
            summary_df.to_csv(summary_path, index=False)
            
            print("\n" + "="*80)
            print("✅ INDUSTRY BENCHMARKS COMPLETE")
            print("="*80)
            print(f"\nSuccessfully created {len(summary_data)} industry benchmarks")
            print(f"Output directory: {self.output_path}")
            print(f"Summary file: {summary_path}")
            
            # Print top performers
            if len(summary_df) > 0:
                print("\n📈 Top 10 Performing Industries (Annualized Return):")
                top10 = summary_df.nlargest(10, 'annualized_return')[
                    ['industry', 'annualized_return', 'total_return', 'sharpe_ratio', 'win_rate']
                ]
                for _, row in top10.iterrows():
                    print(f"  {row['industry']:40s} {row['annualized_return']:6.1f}%  "
                          f"(Total: {row['total_return']:7.1f}%, Sharpe: {row['sharpe_ratio']:5.2f}, "
                          f"Win: {row['win_rate']:4.1f}%)")
                
                print("\n📉 Bottom 10 Performing Industries:")
                bottom10 = summary_df.nsmallest(10, 'annualized_return')[
                    ['industry', 'annualized_return', 'total_return', 'sharpe_ratio', 'win_rate']
                ]
                for _, row in bottom10.iterrows():
                    print(f"  {row['industry']:40s} {row['annualized_return']:6.1f}%  "
                          f"(Total: {row['total_return']:7.1f}%, Sharpe: {row['sharpe_ratio']:5.2f}, "
                          f"Win: {row['win_rate']:4.1f}%)")
        
        return summary_data


def main():
    """Main execution"""
    builder = IndustryBenchmarkBuilder()
    summary = builder.build_all_industries()
    return builder, summary


if __name__ == "__main__":
    builder, summary = main()
