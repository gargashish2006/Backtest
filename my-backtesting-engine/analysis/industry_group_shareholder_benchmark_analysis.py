"""
Industry Group Shareholder Benchmark Analysis

This script analyzes industry group performance based on shareholder trends,
using pre-calculated industry group benchmarks for return calculation.

Key features:
- Uses industry_group field (not industry)
- Calculates returns from industry group benchmarks only
- Rebalances quarterly (mid-Feb, May, Aug, Nov on 15th)
- Selects top/bottom 5 industry groups by % stocks with increasing shareholders
- Tests 5 lookback periods × 3 holding periods = 15 combinations
- Generates matrices and visualizations
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

# Directories
BASE_DIR = Path(__file__).parent.parent
DATABASE_DIR = BASE_DIR / 'database'
RESULTS_DIR = BASE_DIR / 'results'
CHARTS_DIR = BASE_DIR / 'analysis' / 'outputs' / 'charts'
REPORTS_DIR = BASE_DIR / 'analysis' / 'outputs' / 'reports'

# Create output directories
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

class IndustryGroupShareholderAnalyzer:
    """Analyzer for industry group performance based on shareholder trends using benchmarks."""
    
    def __init__(self):
        """Initialize the analyzer and load data."""
        print("=" * 80)
        print("INDUSTRY GROUP SHAREHOLDER BENCHMARK ANALYSIS")
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
        
        self.min_stocks_per_group = 5  # Minimum stocks required for industry group selection
        self.top_n_groups = 5  # Select top/bottom 5 groups
        
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
        # Parse quarter to date
        self.shareholding_df['date'] = self.shareholding_df['quarter'].apply(
            self.parse_quarter_to_date
        )
        self.shareholding_df = self.shareholding_df.sort_values(['isin', 'date'])
        print(f"    Loaded {len(self.shareholding_df):,} shareholding records")
        
        # Load industry info
        print("  - Loading industry information...")
        industry_file = DATABASE_DIR / 'industry_info.csv'
        self.industry_df = pd.read_csv(industry_file)
        # Filter out 'Other' category
        self.industry_df = self.industry_df[self.industry_df['industry_group'] != 'Other']
        print(f"    Loaded {len(self.industry_df):,} industry mappings (excluding 'Other')")
        
        # Create ISIN to industry_group mapping
        self.isin_to_industry = dict(zip(
            self.industry_df['isin'],
            self.industry_df['industry_group']
        ))
        
        # Load industry benchmarks
        print("  - Loading industry benchmarks...")
        benchmark_base_dir = BASE_DIR / 'analysis' / 'outputs' / 'benchmarks' / 'industry_groups'
        
        # Load all timeseries files
        benchmark_dfs = []
        for industry_dir in benchmark_base_dir.iterdir():
            if industry_dir.is_dir():
                timeseries_file = industry_dir / 'timeseries.csv'
                if timeseries_file.exists():
                    df = pd.read_csv(timeseries_file)
                    df['industry_group'] = industry_dir.name.replace('_', ' ')
                    benchmark_dfs.append(df[['industry_group', 'date', 'index_value']])
        
        if not benchmark_dfs:
            raise FileNotFoundError("No benchmark timeseries files found")
        
        self.benchmark_df = pd.concat(benchmark_dfs, ignore_index=True)
        self.benchmark_df['date'] = pd.to_datetime(self.benchmark_df['date'])
        self.benchmark_df = self.benchmark_df.sort_values(['industry_group', 'date'])
        print(f"    Loaded {len(self.benchmark_df):,} benchmark records")
        
        # Create benchmark lookup: {industry_group: {date: index_value}}
        print("  - Creating benchmark lookup dictionary...")
        self.benchmark_lookup = {}
        for industry_group in self.benchmark_df['industry_group'].unique():
            group_data = self.benchmark_df[self.benchmark_df['industry_group'] == industry_group]
            self.benchmark_lookup[industry_group] = dict(zip(
                group_data['date'],
                group_data['index_value']
            ))
        print(f"    Created lookup for {len(self.benchmark_lookup)} industry groups")
        
        # Get unique industry groups
        self.industry_groups = sorted([g for g in self.benchmark_df['industry_group'].unique() 
                                       if g in self.industry_df['industry_group'].values])
        print(f"    Found {len(self.industry_groups)} industry groups for analysis")
        
        # Get benchmark date range
        self.benchmark_min_date = self.benchmark_df['date'].min()
        self.benchmark_max_date = self.benchmark_df['date'].max()
        print(f"    Benchmark date range: {self.benchmark_min_date.strftime('%Y-%m-%d')} to {self.benchmark_max_date.strftime('%Y-%m-%d')}")
        
        # Get all rebalance dates
        self.get_rebalance_dates()
        
        print("\n✓ Data loading complete\n")
        
    def get_rebalance_dates(self):
        """Get all quarterly rebalance dates within benchmark data range."""
        # Use shareholding date range initially
        min_date = self.shareholding_df['date'].min()
        max_date = self.shareholding_df['date'].max()
        
        # But restrict to benchmark availability
        min_date = max(min_date, self.benchmark_min_date - pd.DateOffset(months=6))  # Allow some lookback
        max_date = min(max_date, self.benchmark_max_date)
        
        rebalance_dates = []
        current_year = min_date.year
        max_year = max_date.year
        
        for year in range(current_year, max_year + 1):
            for month in self.rebalance_months:
                date = pd.Timestamp(year=year, month=month, day=self.rebalance_day)
                if min_date <= date <= max_date:
                    rebalance_dates.append(date)
        
        self.rebalance_dates = sorted(rebalance_dates)
        print(f"  - Found {len(self.rebalance_dates)} rebalance dates (filtered to benchmark availability)")
        if len(self.rebalance_dates) > 0:
            print(f"    From {self.rebalance_dates[0].strftime('%Y-%m-%d')} "
                  f"to {self.rebalance_dates[-1].strftime('%Y-%m-%d')}")
        
    def calculate_industry_group_metrics_at_rebalance(
        self, 
        rebalance_date: pd.Timestamp,
        lookback_quarters: int
    ) -> Dict[str, Dict]:
        """
        Calculate shareholder metrics for each industry group at rebalance date.
        
        Returns dict with:
        {
            'industry_group': {
                'num_stocks': int,
                'pct_increasing': float,
                'pct_decreasing': float
            }
        }
        """
        # Get most recent shareholding data before or on rebalance date
        # (shareholding data is quarterly: Mar, Jun, Sep, Dec)
        available_dates = self.shareholding_df[
            self.shareholding_df['date'] <= rebalance_date
        ]['date'].unique()
        
        if len(available_dates) == 0:
            return {}
        
        current_shp_date = max(available_dates)
        current_shp = self.shareholding_df[
            self.shareholding_df['date'] == current_shp_date
        ].copy()
        
        if len(current_shp) == 0:
            return {}
        
        # Get shareholding data from lookback quarters ago (from the current_shp_date)
        lookback_date = current_shp_date - pd.DateOffset(months=lookback_quarters * 3)
        
        # Find the closest actual shareholding date to lookback_date
        available_past_dates = self.shareholding_df[
            self.shareholding_df['date'] <= lookback_date
        ]['date'].unique()
        
        if len(available_past_dates) == 0:
            return {}
        
        past_shp_date = max(available_past_dates)
        past_shp = self.shareholding_df[
            self.shareholding_df['date'] == past_shp_date
        ].copy()
        
        if len(past_shp) == 0:
            return {}
        
        # Merge current and past shareholding
        merged = current_shp.merge(
            past_shp[['isin', 'total_shareholders']],
            on='isin',
            how='inner',
            suffixes=('_current', '_past')
        )
        
        # Add industry group
        merged['industry_group'] = merged['isin'].map(self.isin_to_industry)
        merged = merged.dropna(subset=['industry_group'])
        
        # Calculate change
        merged['shareholder_change'] = (
            merged['total_shareholders_current'] - merged['total_shareholders_past']
        )
        merged['is_increasing'] = merged['shareholder_change'] > 0
        merged['is_decreasing'] = merged['shareholder_change'] < 0
        
        # Group by industry_group
        industry_metrics = {}
        for industry_group in merged['industry_group'].unique():
            group_data = merged[merged['industry_group'] == industry_group]
            num_stocks = len(group_data)
            
            if num_stocks < self.min_stocks_per_group:
                continue
            
            num_increasing = group_data['is_increasing'].sum()
            num_decreasing = group_data['is_decreasing'].sum()
            
            pct_increasing = (num_increasing / num_stocks) * 100
            pct_decreasing = (num_decreasing / num_stocks) * 100
            
            industry_metrics[industry_group] = {
                'num_stocks': num_stocks,
                'pct_increasing': pct_increasing,
                'pct_decreasing': pct_decreasing,
                'num_increasing': num_increasing,
                'num_decreasing': num_decreasing
            }
        
        return industry_metrics
    
    def select_top_bottom_industry_groups(
        self, 
        industry_metrics: Dict[str, Dict]
    ) -> Tuple[List[str], List[str]]:
        """
        Select top and bottom N industry groups by % increasing shareholders.
        
        Returns:
            (top_groups, bottom_groups) - Lists of industry group names
        """
        if not industry_metrics:
            return [], []
        
        # Sort by pct_increasing
        sorted_groups = sorted(
            industry_metrics.items(),
            key=lambda x: x[1]['pct_increasing'],
            reverse=True
        )
        
        # Top N groups (highest % increasing)
        top_groups = [group for group, _ in sorted_groups[:self.top_n_groups]]
        
        # Bottom N groups (lowest % increasing = highest % decreasing)
        bottom_groups = [group for group, _ in sorted_groups[-self.top_n_groups:]]
        
        return top_groups, bottom_groups
    
    def calculate_benchmark_return(
        self,
        industry_group: str,
        entry_date: pd.Timestamp,
        holding_days: int
    ) -> float:
        """
        Calculate return for an industry group using benchmark values.
        
        Returns percentage return over the holding period, or np.nan if data unavailable.
        """
        exit_date = entry_date + pd.Timedelta(days=holding_days)
        
        # Get benchmark values
        if industry_group not in self.benchmark_lookup:
            return np.nan
        
        benchmark_dict = self.benchmark_lookup[industry_group]
        
        # Find entry benchmark value (exact date or nearest before, within 60 days)
        entry_dates = [d for d in benchmark_dict.keys() 
                      if entry_date - pd.Timedelta(days=60) <= d <= entry_date]
        if not entry_dates:
            return np.nan
        entry_benchmark_date = max(entry_dates)
        entry_value = benchmark_dict[entry_benchmark_date]
        
        # Find exit benchmark value (exact date or nearest after, within 60 days)
        exit_dates = [d for d in benchmark_dict.keys() 
                     if exit_date <= d <= exit_date + pd.Timedelta(days=60)]
        if not exit_dates:
            return np.nan
        exit_benchmark_date = min(exit_dates)
        exit_value = benchmark_dict[exit_benchmark_date]
        
        if pd.isna(entry_value) or pd.isna(exit_value) or entry_value <= 0:
            return np.nan
        
        # Calculate percentage return
        pct_return = ((exit_value - entry_value) / entry_value) * 100
        
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
        print(f"  - Min stocks per group: {self.min_stocks_per_group}")
        print(f"  - Top/Bottom N groups: {self.top_n_groups}")
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
    ) -> List[Dict]:
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
            if exit_date > self.benchmark_df['date'].max():
                continue
            
            valid_rebalance_dates.append(rebalance_date)
        
        print(f"  Processing {len(valid_rebalance_dates)} rebalance dates...")
        
        for idx, rebalance_date in enumerate(valid_rebalance_dates, 1):
            if idx % 5 == 0 or idx == len(valid_rebalance_dates):
                print(f"    Rebalance {idx}/{len(valid_rebalance_dates)}: "
                      f"{rebalance_date.strftime('%Y-%m-%d')}")
            
            # Calculate industry group metrics
            industry_metrics = self.calculate_industry_group_metrics_at_rebalance(
                rebalance_date, lookback_quarters
            )
            
            if not industry_metrics:
                continue
            
            # Select top and bottom groups
            top_groups, bottom_groups = self.select_top_bottom_industry_groups(
                industry_metrics
            )
            
            # Calculate returns for top groups (increasing shareholders)
            for group in top_groups:
                ret = self.calculate_benchmark_return(
                    group, rebalance_date, holding_days
                )
                
                if not pd.isna(ret):
                    results.append({
                        'rebalance_date': rebalance_date,
                        'lookback': lookback_name,
                        'holding': holding_name,
                        'industry_group': group,
                        'category': 'Top (Increasing)',
                        'pct_increasing': industry_metrics[group]['pct_increasing'],
                        'num_stocks': industry_metrics[group]['num_stocks'],
                        'forward_return': ret
                    })
            
            # Calculate returns for bottom groups (decreasing shareholders)
            for group in bottom_groups:
                ret = self.calculate_benchmark_return(
                    group, rebalance_date, holding_days
                )
                
                if not pd.isna(ret):
                    results.append({
                        'rebalance_date': rebalance_date,
                        'lookback': lookback_name,
                        'holding': holding_name,
                        'industry_group': group,
                        'category': 'Bottom (Decreasing)',
                        'pct_increasing': industry_metrics[group]['pct_increasing'],
                        'num_stocks': industry_metrics[group]['num_stocks'],
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
            print("This could be due to:")
            print("  - Benchmark data not available for selected time periods")
            print("  - Industry group naming mismatches")
            print("  - Insufficient stocks per industry group")
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
        summary_file = REPORTS_DIR / f'industry_group_summary_{timestamp}.csv'
        self.summary_df.to_csv(summary_file, index=False)
        print(f"\n✓ Saved summary to {summary_file}")
        
        # Save detailed results
        detailed_file = REPORTS_DIR / f'industry_group_detailed_{timestamp}.csv'
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
        chart_file = CHARTS_DIR / f'industry_group_heatmaps_{timestamp}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved heatmaps to {chart_file}")
        plt.close()
    
    def plot_comparison_charts(self):
        """Create comparison charts between top and bottom groups."""
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
        chart_file = CHARTS_DIR / f'industry_group_comparison_{timestamp}.png'
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved comparison charts to {chart_file}")
        plt.close()


def main():
    """Main execution function."""
    analyzer = IndustryGroupShareholderAnalyzer()
    results = analyzer.run_comprehensive_analysis()
    
    print("\n" + "=" * 80)
    print("ALL PROCESSING COMPLETE")
    print("=" * 80)
    print(f"\nTotal return observations: {len(results):,}")
    print(f"Charts saved to: {CHARTS_DIR}")
    print(f"Reports saved to: {REPORTS_DIR}")
    print("\n✓ Industry group shareholder benchmark analysis complete!")


if __name__ == "__main__":
    main()
