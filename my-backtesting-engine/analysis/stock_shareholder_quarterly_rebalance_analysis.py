"""
Stock-Level Shareholder Analysis with Quarterly Rebalancing

Analyzes individual STOCKS based on shareholder changes.
Uses same rebalancing methodology as industry-level analysis.

Rebalance Dates: Mid-Feb, Mid-May, Mid-Aug, Mid-Nov (quarterly)
Strategy: Select top/bottom N stocks by shareholder changes
Filter: Only stocks above 200-day moving average
Returns: Calculated from individual stock price changes
Shareholding: Uses previous quarter data (e.g., Dec 2024 for Feb 2025 rebalance)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# Directories
BASE_DIR = Path(__file__).parent.parent
DATABASE_DIR = BASE_DIR / 'database'
CHARTS_DIR = BASE_DIR / 'analysis' / 'outputs' / 'charts'
REPORTS_DIR = BASE_DIR / 'analysis' / 'outputs' / 'reports'

# Create output directories
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class StockShareholderQuarterlyAnalyzer:
    """Analyzer for stock performance based on shareholder trends with quarterly rebalancing."""
    
    def __init__(self):
        """Initialize the analyzer and load data."""
        print("=" * 80)
        print("STOCK SHAREHOLDER QUARTERLY REBALANCING ANALYSIS")
        print("=" * 80)
        print("\nInitializing analyzer...")
        
        # Configuration
        self.lookback_periods = {
            '3M': 1,   # 1 quarter
            '6M': 2,   # 2 quarters
            '12M': 4,  # 4 quarters
            '24M': 8,  # 8 quarters
            '36M': 12  # 12 quarters
        }
        
        self.holding_periods = {
            '90D': 90,
            '180D': 180,
            '365D': 365
        }
        
        # Rebalancing months (mid-month)
        self.rebalance_months = [2, 5, 8, 11]  # Feb, May, Aug, Nov
        self.rebalance_day = 15
        
        self.top_n_stocks = 50  # Select top/bottom 50 stocks
        
        # Load data
        self.load_data()
        
    def parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings (like 'Mar-2020') to quarter-end dates."""
        try:
            if '-' in str(quarter_str):
                parts = str(quarter_str).split('-')
                if len(parts) == 2:
                    month_str, year_str = parts
                    month_map = {
                        'Mar': 3, 'Jun': 6, 'Sep': 9, 'Dec': 12,
                        'March': 3, 'June': 6, 'September': 9, 'December': 12
                    }
                    month = month_map.get(month_str, 12)
                    year = int(year_str)
                    from calendar import monthrange
                    day = monthrange(year, month)[1]
                    return pd.Timestamp(year=year, month=month, day=day)
            return pd.NaT
        except:
            return pd.NaT
    
    def load_data(self):
        """Load all required data files."""
        print("\nLoading data files...")
        
        # Load shareholding patterns
        print("  - Loading shareholding patterns...")
        shp_file = DATABASE_DIR / 'shareholding_patterns.csv'
        self.shareholding_df = pd.read_csv(shp_file)
        self.shareholding_df['date'] = self.shareholding_df['quarter'].apply(
            self.parse_quarter_to_date
        )
        self.shareholding_df = self.shareholding_df.sort_values(['isin', 'date'])
        print(f"    Loaded {len(self.shareholding_df):,} shareholding records")
        
        # Load price data
        print("  - Loading price data...")
        price_file = DATABASE_DIR / 'price_data.csv'
        self.price_df = pd.read_csv(
            price_file,
            parse_dates=['date'],
            dtype={'isin': 'str', 'close': 'float32'}
        )
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        print(f"    Loaded {len(self.price_df):,} price records")
        
        # Calculate 200-day MA
        print("  - Calculating 200-day moving averages...")
        self.price_df['ma_200'] = self.price_df.groupby('isin')['close'].transform(
            lambda x: x.rolling(window=200, min_periods=200).mean()
        )
        self.price_df['above_ma'] = self.price_df['close'] > self.price_df['ma_200']
        print(f"    Calculated 200-day MA for all stocks")
        
        # Get price date range
        self.price_min_date = self.price_df['date'].min()
        self.price_max_date = self.price_df['date'].max()
        print(f"    Price date range: {self.price_min_date.strftime('%Y-%m-%d')} to {self.price_max_date.strftime('%Y-%m-%d')}")
        
        # Create price lookup for faster access (optimized with groupby)
        print("  - Creating price lookup dictionary...")
        self.price_lookup = {}
        grouped = self.price_df.groupby('isin')
        for isin, isin_data in grouped:
            self.price_lookup[isin] = dict(zip(
                isin_data['date'],
                zip(isin_data['close'], isin_data['above_ma'])
            ))
        print(f"    Created lookup for {len(self.price_lookup):,} stocks")
        
        # Get all rebalance dates
        self.get_rebalance_dates()
        
        # Pre-compute stocks above MA at each rebalance date
        print("  - Pre-computing stocks above 200-day MA at rebalance dates...")
        self.precompute_ma_status()
        
        print("\n✓ Data loading complete\n")
        
    def get_rebalance_dates(self):
        """Get all quarterly rebalance dates within data range."""
        # Use price data range
        min_date = max(self.shareholding_df['date'].min(), self.price_min_date)
        max_date = min(self.shareholding_df['date'].max(), self.price_max_date)
        
        rebalance_dates = []
        current_year = min_date.year
        max_year = max_date.year
        
        for year in range(current_year, max_year + 1):
            for month in self.rebalance_months:
                date = pd.Timestamp(year=year, month=month, day=self.rebalance_day)
                if min_date <= date <= max_date:
                    rebalance_dates.append(date)
        
        self.rebalance_dates = sorted(rebalance_dates)
        print(f"  - Found {len(self.rebalance_dates)} rebalance dates")
        if len(self.rebalance_dates) > 0:
            print(f"    From {self.rebalance_dates[0].strftime('%Y-%m-%d')} "
                  f"to {self.rebalance_dates[-1].strftime('%Y-%m-%d')}")
    
    def precompute_ma_status(self):
        """Pre-compute which stocks are above 200-day MA at each rebalance date."""
        self.stocks_above_ma = {}  # {rebalance_date: set of ISINs above MA}
        
        # Create a sorted copy of price data for efficient date lookups
        price_sorted = self.price_df[['isin', 'date', 'above_ma']].copy()
        price_sorted = price_sorted[price_sorted['above_ma'].notna()]  # Filter out NaN MA values
        price_sorted = price_sorted.sort_values(['isin', 'date'])
        
        for rebalance_date in self.rebalance_dates:
            # Find all price records within ±7 days of rebalance date
            date_min = rebalance_date - pd.Timedelta(days=7)
            date_max = rebalance_date + pd.Timedelta(days=7)
            
            nearby_prices = price_sorted[
                (price_sorted['date'] >= date_min) &
                (price_sorted['date'] <= date_max)
            ].copy()
            
            # For each ISIN, find the nearest date
            nearby_prices['date_diff'] = (nearby_prices['date'] - rebalance_date).abs()
            nearest = nearby_prices.loc[nearby_prices.groupby('isin')['date_diff'].idxmin()]
            
            # Get ISINs above MA
            stocks_above = set(nearest[nearest['above_ma'] == True]['isin'].unique())
            
            self.stocks_above_ma[rebalance_date] = stocks_above
        
        print(f"    Pre-computed MA status for {len(self.rebalance_dates)} rebalance dates")
    
    def calculate_stock_metrics_at_rebalance(
        self, 
        rebalance_date: pd.Timestamp,
        lookback_quarters: int
    ):
        """
        Calculate shareholder change metrics for each stock at rebalance date.
        Returns DataFrame with stock-level metrics.
        """
        # Get most recent shareholding data before or on rebalance date
        available_dates = self.shareholding_df[
            self.shareholding_df['date'] <= rebalance_date
        ]['date'].unique()
        
        if len(available_dates) == 0:
            return None
        
        current_shp_date = max(available_dates)
        current_shp = self.shareholding_df[
            self.shareholding_df['date'] == current_shp_date
        ].copy()
        
        if len(current_shp) == 0:
            return None
        
        # Get shareholding data from lookback quarters ago
        lookback_date = current_shp_date - pd.DateOffset(months=lookback_quarters * 3)
        
        # Find the closest actual shareholding date
        available_past_dates = self.shareholding_df[
            self.shareholding_df['date'] <= lookback_date
        ]['date'].unique()
        
        if len(available_past_dates) == 0:
            return None
        
        past_shp_date = max(available_past_dates)
        past_shp = self.shareholding_df[
            self.shareholding_df['date'] == past_shp_date
        ].copy()
        
        if len(past_shp) == 0:
            return None
        
        # Merge current and past shareholding
        merged = current_shp.merge(
            past_shp[['isin', 'total_shareholders']],
            on='isin',
            how='inner',
            suffixes=('_current', '_past')
        )
        
        # Calculate change
        merged['shareholder_change'] = (
            merged['total_shareholders_current'] - merged['total_shareholders_past']
        )
        merged['pct_change'] = (
            merged['shareholder_change'] / merged['total_shareholders_past'] * 100
        )
        
        # Filter only stocks above 200-day MA at rebalance date
        stocks_above_ma = self.stocks_above_ma.get(rebalance_date, set())
        merged = merged[merged['isin'].isin(stocks_above_ma)].copy()
        
        return merged[['isin', 'shareholder_change', 'pct_change', 'total_shareholders_current']]
    
    def get_stock_above_ma(self, isin: str, date: pd.Timestamp):
        """Check if stock is above 200-day MA at given date."""
        if isin not in self.price_lookup:
            return False
        
        price_dict = self.price_lookup[isin]
        
        # Find nearest date within ±7 days
        nearby_dates = [d for d in price_dict.keys() 
                       if date - pd.Timedelta(days=7) <= d <= date + pd.Timedelta(days=7)]
        
        if not nearby_dates:
            return False
        
        nearest_date = min(nearby_dates, key=lambda d: abs((d - date).days))
        _, above_ma = price_dict[nearest_date]
        
        return above_ma if not pd.isna(above_ma) else False
    
    def select_top_bottom_stocks(self, stock_metrics, n=50):
        """
        Select top N and bottom N stocks by shareholder change percentage.
        
        Returns:
            (top_isins, bottom_isins) - Lists of ISINs
        """
        if stock_metrics is None or len(stock_metrics) == 0:
            return [], []
        
        if len(stock_metrics) < n * 2:
            n = max(1, len(stock_metrics) // 2)
        
        # Sort by percentage change
        sorted_stocks = stock_metrics.sort_values('pct_change', ascending=False)
        
        # Top N (highest % increase)
        top_isins = sorted_stocks.head(n)['isin'].tolist()
        
        # Bottom N (lowest % increase = highest % decrease)
        bottom_isins = sorted_stocks.tail(n)['isin'].tolist()
        
        return top_isins, bottom_isins
    
    def calculate_stock_return(self, isin: str, entry_date: pd.Timestamp, holding_days: int):
        """
        Calculate return for a stock.
        
        Returns percentage return over the holding period, or np.nan if data unavailable.
        """
        if isin not in self.price_lookup:
            return np.nan
        
        price_dict = self.price_lookup[isin]
        
        # Find entry price (within ±7 days)
        entry_dates = [d for d in price_dict.keys() 
                      if entry_date - pd.Timedelta(days=7) <= d <= entry_date + pd.Timedelta(days=7)]
        if not entry_dates:
            return np.nan
        
        entry_date_actual = min(entry_dates, key=lambda d: abs((d - entry_date).days))
        entry_price, _ = price_dict[entry_date_actual]
        
        # Find exit price
        exit_date = entry_date + pd.Timedelta(days=holding_days)
        exit_dates = [d for d in price_dict.keys() 
                     if exit_date - pd.Timedelta(days=7) <= d <= exit_date + pd.Timedelta(days=7)]
        if not exit_dates:
            return np.nan
        
        exit_date_actual = min(exit_dates, key=lambda d: abs((d - exit_date).days))
        exit_price, _ = price_dict[exit_date_actual]
        
        if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
            return np.nan
        
        # Calculate percentage return
        pct_return = ((exit_price - entry_price) / entry_price) * 100
        
        return pct_return
    
    def run_comprehensive_analysis(self):
        """Run analysis for all combinations of lookback and holding periods."""
        print("=" * 80)
        print("RUNNING COMPREHENSIVE ANALYSIS")
        print("=" * 80)
        print(f"\nConfiguration:")
        print(f"  - Lookback periods: {list(self.lookback_periods.keys())}")
        print(f"  - Holding periods: {list(self.holding_periods.keys())}")
        print(f"  - Rebalance dates: {len(self.rebalance_dates)}")
        print(f"  - Top/Bottom N stocks: {self.top_n_stocks}")
        print(f"  - Filter: Stocks above 200-day MA only")
        print(f"  - Total combinations: {len(self.lookback_periods) * len(self.holding_periods)}")
        
        results = []
        
        total_combinations = len(self.lookback_periods) * len(self.holding_periods)
        combo_num = 0
        
        for lookback_name, lookback_quarters in self.lookback_periods.items():
            for holding_name, holding_days in self.holding_periods.items():
                combo_num += 1
                print(f"\n{'=' * 80}")
                print(f"Combination {combo_num}/{total_combinations}: "
                      f"Lookback={lookback_name}, Holding={holding_name}")
                print(f"{'=' * 80}")
                
                combo_results = self.analyze_combination(
                    lookback_name, lookback_quarters,
                    holding_name, holding_days
                )
                
                results.extend(combo_results)
        
        # Convert to DataFrame
        self.results_df = pd.DataFrame(results)
        
        print(f"\n{'=' * 80}")
        print("ANALYSIS COMPLETE")
        print(f"{'=' * 80}")
        print(f"Total observations: {len(self.results_df):,}")
        
        if len(self.results_df) > 0:
            # Generate summary and visualizations
            self.generate_summary()
            self.plot_heatmaps()
            self.plot_comparison_charts()
        
        return self.results_df
    
    def analyze_combination(
        self,
        lookback_name: str,
        lookback_quarters: int,
        holding_name: str,
        holding_days: int
    ):
        """Analyze a single combination of lookback and holding period."""
        results = []
        
        valid_rebalance_dates = []
        for rebalance_date in self.rebalance_dates:
            # Check if we have enough history for lookback
            min_date_needed = rebalance_date - pd.DateOffset(months=lookback_quarters * 3)
            if min_date_needed < self.shareholding_df['date'].min():
                continue
            
            # Check if we can calculate forward returns
            exit_date = rebalance_date + pd.Timedelta(days=holding_days)
            if exit_date > self.price_max_date:
                continue
            
            valid_rebalance_dates.append(rebalance_date)
        
        print(f"  Processing {len(valid_rebalance_dates)} rebalance dates...")
        
        for idx, rebalance_date in enumerate(valid_rebalance_dates, 1):
            if idx % 10 == 0 or idx == len(valid_rebalance_dates):
                print(f"    Rebalance {idx}/{len(valid_rebalance_dates)}: "
                      f"{rebalance_date.strftime('%Y-%m-%d')}")
            
            # Calculate stock metrics
            stock_metrics = self.calculate_stock_metrics_at_rebalance(
                rebalance_date, lookback_quarters
            )
            
            if stock_metrics is None or len(stock_metrics) == 0:
                continue
            
            # Select top and bottom stocks
            top_isins, bottom_isins = self.select_top_bottom_stocks(
                stock_metrics, n=self.top_n_stocks
            )
            
            # Calculate returns for top stocks (increasing shareholders)
            for isin in top_isins:
                ret = self.calculate_stock_return(isin, rebalance_date, holding_days)
                
                if not pd.isna(ret):
                    stock_data = stock_metrics[stock_metrics['isin'] == isin].iloc[0]
                    results.append({
                        'rebalance_date': rebalance_date,
                        'lookback': lookback_name,
                        'holding': holding_name,
                        'isin': isin,
                        'category': 'Top (Increasing)',
                        'pct_change': stock_data['pct_change'],
                        'shareholder_change': stock_data['shareholder_change'],
                        'forward_return': ret
                    })
            
            # Calculate returns for bottom stocks (decreasing shareholders)
            for isin in bottom_isins:
                ret = self.calculate_stock_return(isin, rebalance_date, holding_days)
                
                if not pd.isna(ret):
                    stock_data = stock_metrics[stock_metrics['isin'] == isin].iloc[0]
                    results.append({
                        'rebalance_date': rebalance_date,
                        'lookback': lookback_name,
                        'holding': holding_name,
                        'isin': isin,
                        'category': 'Bottom (Decreasing)',
                        'pct_change': stock_data['pct_change'],
                        'shareholder_change': stock_data['shareholder_change'],
                        'forward_return': ret
                    })
        
        print(f"  ✓ Collected {len(results)} return observations")
        
        return results
    
    def generate_summary(self):
        """Generate summary statistics."""
        print("\n" + "=" * 80)
        print("GENERATING SUMMARY")
        print("=" * 80)
        
        if len(self.results_df) == 0:
            print("\n⚠️  No return observations collected. Cannot generate summary.")
            return
        
        summary_rows = []
        
        for lookback in self.lookback_periods.keys():
            for holding in self.holding_periods.keys():
                subset = self.results_df[
                    (self.results_df['lookback'] == lookback) &
                    (self.results_df['holding'] == holding)
                ]
                
                if len(subset) == 0:
                    continue
                
                for category in ['Top (Increasing)', 'Bottom (Decreasing)']:
                    cat_data = subset[subset['category'] == category]
                    
                    if len(cat_data) == 0:
                        continue
                    
                    returns = cat_data['forward_return'].dropna()
                    
                    if len(returns) == 0:
                        continue
                    
                    summary_rows.append({
                        'lookback': lookback,
                        'holding': holding,
                        'category': category,
                        'count': len(returns),
                        'mean_return': returns.mean(),
                        'median_return': returns.median(),
                        'std_return': returns.std(),
                        'min_return': returns.min(),
                        'max_return': returns.max(),
                        'pct_positive': (returns > 0).sum() / len(returns) * 100,
                        'sharpe': returns.mean() / returns.std() if returns.std() > 0 else 0
                    })
        
        self.summary_df = pd.DataFrame(summary_rows)
        
        # Save summary
        timestamp = datetime.now().strftime('%Y%m%d')
        summary_file = REPORTS_DIR / f'stock_quarterly_summary_{timestamp}.csv'
        self.summary_df.to_csv(summary_file, index=False)
        print(f"\n✓ Saved summary to {summary_file}")
        
        # Save detailed results
        detailed_file = REPORTS_DIR / f'stock_quarterly_detailed_{timestamp}.csv'
        self.results_df.to_csv(detailed_file, index=False)
        print(f"✓ Saved detailed results to {detailed_file}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY BY COMBINATION")
        print("=" * 80)
        
        for _, row in self.summary_df.iterrows():
            print(f"\n{row['lookback']} Lookback, {row['holding']} Holding - {row['category']}")
            print(f"  Count: {row['count']}")
            print(f"  Mean Return: {row['mean_return']:.2f}%")
            print(f"  Median Return: {row['median_return']:.2f}%")
            print(f"  Std Dev: {row['std_return']:.2f}%")
            print(f"  Win Rate: {row['pct_positive']:.1f}%")
            print(f"  Sharpe: {row['sharpe']:.2f}")
        
        # Create return matrices
        self.create_return_matrices()
    
    def create_return_matrices(self):
        """Create matrices of returns with lookback in rows and holding in columns."""
        print("\n" + "=" * 80)
        print("RETURN MATRICES")
        print("=" * 80)
        
        lookback_order = ['3M', '6M', '12M', '24M', '36M']
        holding_order = ['90D', '180D', '365D']
        
        for category in ['Top (Increasing)', 'Bottom (Decreasing)']:
            print(f"\n{category}:")
            print("-" * 60)
            
            matrix_data = []
            for lookback in lookback_order:
                row = []
                for holding in holding_order:
                    subset = self.summary_df[
                        (self.summary_df['lookback'] == lookback) &
                        (self.summary_df['holding'] == holding) &
                        (self.summary_df['category'] == category)
                    ]
                    
                    if len(subset) > 0:
                        mean_return = subset['mean_return'].iloc[0]
                        row.append(f"{mean_return:.2f}%")
                    else:
                        row.append("N/A")
                
                matrix_data.append(row)
            
            # Print matrix
            header = "Lookback \\ Holding | " + " | ".join([f"{h:>10}" for h in holding_order])
            print(header)
            print("-" * len(header))
            
            for lookback, row in zip(lookback_order, matrix_data):
                row_str = f"{lookback:>18} | " + " | ".join([f"{val:>10}" for val in row])
                print(row_str)
    
    def plot_heatmaps(self):
        """Create heatmaps for mean returns."""
        print("\n" + "=" * 80)
        print("GENERATING HEATMAPS")
        print("=" * 80)
        
        if len(self.results_df) == 0:
            print("⚠️  No data to plot. Skipping heatmaps.")
            return
        
        lookback_order = ['3M', '6M', '12M', '24M', '36M']
        holding_order = ['90D', '180D', '365D']
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        for idx, category in enumerate(['Top (Increasing)', 'Bottom (Decreasing)']):
            # Create matrix
            matrix = []
            for lookback in lookback_order:
                row = []
                for holding in holding_order:
                    subset = self.summary_df[
                        (self.summary_df['lookback'] == lookback) &
                        (self.summary_df['holding'] == holding) &
                        (self.summary_df['category'] == category)
                    ]
                    
                    if len(subset) > 0:
                        row.append(subset['mean_return'].iloc[0])
                    else:
                        row.append(np.nan)
                
                matrix.append(row)
            
            # Plot heatmap
            ax = axes[idx]
            sns.heatmap(
                matrix,
                annot=True,
                fmt='.2f',
                xticklabels=holding_order,
                yticklabels=lookback_order,
                cmap='RdYlGn',
                center=0,
                ax=ax,
                cbar_kws={'label': 'Mean Return (%)'}
            )
            ax.set_title(f'{category}\nMean Returns (%)', fontsize=12, fontweight='bold')
            ax.set_xlabel('Holding Period', fontsize=10)
            ax.set_ylabel('Lookback Period', fontsize=10)
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime('%Y%m%d')
        chart_file = CHARTS_DIR / f'stock_quarterly_heatmaps_{timestamp}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved heatmaps to {chart_file}")
        plt.close()
    
    def plot_comparison_charts(self):
        """Create comparison charts between top and bottom stocks."""
        print("\n" + "=" * 80)
        print("GENERATING COMPARISON CHARTS")
        print("=" * 80)
        
        if len(self.results_df) == 0:
            print("⚠️  No data to plot. Skipping comparison charts.")
            return
        
        lookback_order = ['3M', '6M', '12M', '24M', '36M']
        holding_order = ['90D', '180D', '365D']
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        axes = axes.flatten()
        
        for idx, holding in enumerate(holding_order):
            # Mean returns
            ax = axes[idx]
            
            top_means = []
            bottom_means = []
            
            for lookback in lookback_order:
                top_data = self.summary_df[
                    (self.summary_df['lookback'] == lookback) &
                    (self.summary_df['holding'] == holding) &
                    (self.summary_df['category'] == 'Top (Increasing)')
                ]
                
                bottom_data = self.summary_df[
                    (self.summary_df['lookback'] == lookback) &
                    (self.summary_df['holding'] == holding) &
                    (self.summary_df['category'] == 'Bottom (Decreasing)')
                ]
                
                top_means.append(top_data['mean_return'].iloc[0] if len(top_data) > 0 else 0)
                bottom_means.append(bottom_data['mean_return'].iloc[0] if len(bottom_data) > 0 else 0)
            
            x = np.arange(len(lookback_order))
            width = 0.35
            
            ax.bar(x - width/2, top_means, width, label='Top (Increasing)', color='steelblue', alpha=0.8)
            ax.bar(x + width/2, bottom_means, width, label='Bottom (Decreasing)', color='coral', alpha=0.8)
            
            ax.set_xlabel('Lookback Period', fontsize=10)
            ax.set_ylabel('Mean Return (%)', fontsize=10)
            ax.set_title(f'{holding} Holding Period\nMean Returns', fontsize=11, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(lookback_order)
            ax.legend(fontsize=8)
            ax.grid(axis='y', alpha=0.3)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            # Win rates
            ax = axes[idx + 3]
            
            top_wins = []
            bottom_wins = []
            
            for lookback in lookback_order:
                top_data = self.summary_df[
                    (self.summary_df['lookback'] == lookback) &
                    (self.summary_df['holding'] == holding) &
                    (self.summary_df['category'] == 'Top (Increasing)')
                ]
                
                bottom_data = self.summary_df[
                    (self.summary_df['lookback'] == lookback) &
                    (self.summary_df['holding'] == holding) &
                    (self.summary_df['category'] == 'Bottom (Decreasing)')
                ]
                
                top_wins.append(top_data['pct_positive'].iloc[0] if len(top_data) > 0 else 0)
                bottom_wins.append(bottom_data['pct_positive'].iloc[0] if len(bottom_data) > 0 else 0)
            
            ax.bar(x - width/2, top_wins, width, label='Top (Increasing)', color='steelblue', alpha=0.8)
            ax.bar(x + width/2, bottom_wins, width, label='Bottom (Decreasing)', color='coral', alpha=0.8)
            
            ax.set_xlabel('Lookback Period', fontsize=10)
            ax.set_ylabel('Win Rate (%)', fontsize=10)
            ax.set_title(f'{holding} Holding Period\nWin Rates', fontsize=11, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(lookback_order)
            ax.legend(fontsize=8)
            ax.grid(axis='y', alpha=0.3)
            ax.set_ylim([0, 100])
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime('%Y%m%d')
        chart_file = CHARTS_DIR / f'stock_quarterly_comparison_{timestamp}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved comparison charts to {chart_file}")
        plt.close()


def main():
    """Main execution function."""
    analyzer = StockShareholderQuarterlyAnalyzer()
    results = analyzer.run_comprehensive_analysis()
    
    print("\n" + "=" * 80)
    print("ALL PROCESSING COMPLETE")
    print("=" * 80)
    print(f"\nTotal return observations: {len(results):,}")
    print(f"Charts saved to: {CHARTS_DIR}")
    print(f"Reports saved to: {REPORTS_DIR}")
    print("\n✓ Stock shareholder quarterly rebalancing analysis complete!")


if __name__ == "__main__":
    main()
