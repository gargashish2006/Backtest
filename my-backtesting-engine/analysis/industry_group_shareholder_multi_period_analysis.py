#!/usr/bin/env python
"""
Industry Group Shareholder Analysis - Multi-Period (2Q, 1Y, 2Y, 5Y)

Analyzes which industry GROUPS are gaining/losing shareholders across different time horizons:
- 2 Quarters (6 months)
- 1 Year (4 quarters)
- 2 Years (8 quarters)
- 5 Years (20 quarters)

Purpose: Identify broader industry groups with sustained shareholder growth patterns
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class IndustryGroupMultiPeriodAnalyzer:
    """Analyze industry group shareholder changes across multiple time periods"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        # Define periods
        self.periods = {
            '2Q (6M)': 2,
            '1Y': 4,
            '2Y': 8,
            '5Y': 20
        }
        
        print("Loading data...")
        self._load_data()
    
    def _load_data(self):
        """Load required data"""
        # Shareholding patterns
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv'
        )
        
        # Industry info (using industry_group)
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'industry_group']
        )
        
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"Loaded {len(self.industry_df):,} industry mappings")
    
    def _parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings to quarter-end dates"""
        try:
            if 'Q' in str(quarter_str) and 'FY' in str(quarter_str):
                parts = quarter_str.split()
                quarter_num = int(parts[0].replace('Q', ''))
                fy_year = int(parts[1].replace('FY', ''))
                
                quarter_end_months = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}
                month, day = quarter_end_months[quarter_num]
                
                if quarter_num == 4:
                    year = fy_year
                else:
                    year = fy_year - 1
                
                return pd.Timestamp(year=year, month=month, day=day)
            else:
                return pd.to_datetime(quarter_str)
        except Exception as e:
            return None
    
    def prepare_data(self):
        """Prepare data with industry group mapping and quarter dates"""
        print("\nPreparing data...")
        
        # Merge with industry group
        df = self.shareholding_df.merge(
            self.industry_df,
            on='isin',
            how='left'
        )
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        df['quarter_date'] = df['quarter'].apply(self._parse_quarter_to_date)
        
        # Remove invalid data
        df = df.dropna(subset=['quarter_date', 'total_shareholders', 'industry_group'])
        df = df[df['total_shareholders'] > 0]
        df = df[df['industry_group'] != 'Not Available']
        
        # Sort
        df = df.sort_values(['isin', 'quarter_date'])
        
        print(f"  Valid records: {len(df):,}")
        print(f"  Industry Groups: {df['industry_group'].nunique()}")
        print(f"  Date range: {df['quarter_date'].min().date()} to {df['quarter_date'].max().date()}")
        
        self.prepared_df = df
        
        return df
    
    def analyze_period(self, quarters_back):
        """
        Analyze shareholder changes for a specific lookback period
        
        Args:
            quarters_back: Number of quarters to look back (2, 4, 8, 20)
        
        Returns:
            DataFrame with industry group rankings for this period
        """
        print(f"\n  Analyzing {quarters_back}-quarter lookback...")
        
        df = self.prepared_df.copy()
        
        # Calculate shareholders N quarters ago
        df[f'shareholders_{quarters_back}q_ago'] = df.groupby('isin')['total_shareholders'].shift(quarters_back)
        df[f'change_{quarters_back}q'] = df['total_shareholders'] - df[f'shareholders_{quarters_back}q_ago']
        df[f'is_increase_{quarters_back}q'] = df[f'change_{quarters_back}q'] > 0
        
        # Get latest quarter with substantial data (at least 1000 stocks)
        quarter_counts = df.groupby('quarter_date').size()
        substantial_quarters = quarter_counts[quarter_counts >= 1000].index
        
        if len(substantial_quarters) == 0:
            print(f"    ⚠️ No quarters with sufficient data")
            return None
        
        latest_quarter = substantial_quarters.max()
        latest_data = df[df['quarter_date'] == latest_quarter].copy()
        
        # Remove stocks without lookback data
        latest_data = latest_data.dropna(subset=[f'shareholders_{quarters_back}q_ago'])
        
        if len(latest_data) == 0:
            print(f"    ⚠️ No data available for {quarters_back}Q lookback")
            return None
        
        # Calculate by industry group
        group_stats = latest_data.groupby('industry_group').agg({
            'isin': 'count',
            f'is_increase_{quarters_back}q': ['sum', 'mean'],
            f'change_{quarters_back}q': ['mean', 'median']
        }).round(4)
        
        # Flatten column names
        group_stats.columns = ['num_stocks', 'num_increasing', 'pct_increasing', 'avg_change', 'median_change']
        group_stats['pct_increasing'] = group_stats['pct_increasing'] * 100
        
        # Sort by percentage increasing
        group_stats = group_stats.sort_values('pct_increasing', ascending=False)
        
        # Filter out groups with too few stocks (use lower threshold since groups are broader)
        group_stats = group_stats[group_stats['num_stocks'] >= 3]
        
        print(f"    ✅ Analyzed {len(group_stats)} industry groups")
        print(f"    Latest quarter: {latest_quarter.date()}")
        print(f"    Stocks with data: {len(latest_data)}")
        
        return group_stats
    
    def analyze_all_periods(self):
        """Analyze all time periods"""
        print("\n" + "="*80)
        print("ANALYZING ALL TIME PERIODS")
        print("="*80)
        
        results = {}
        
        for period_name, quarters_back in self.periods.items():
            print(f"\n{period_name} ({quarters_back} quarters back):")
            stats = self.analyze_period(quarters_back)
            if stats is not None:
                results[period_name] = stats
        
        self.period_results = results
        return results
    
    def get_top_bottom_rankings(self, n=10):
        """Get top and bottom N industry groups for each period"""
        rankings = {}
        
        for period_name, stats in self.period_results.items():
            # Adjust n if fewer groups available
            actual_n = min(n, len(stats))
            rankings[period_name] = {
                'top': stats.head(actual_n),
                'bottom': stats.tail(actual_n)[::-1]  # Reverse order for bottom
            }
        
        return rankings
    
    def print_rankings(self, n=10):
        """Print formatted rankings for all periods"""
        print("\n" + "="*80)
        print("INDUSTRY GROUP RANKINGS - MULTI-PERIOD ANALYSIS")
        print("="*80)
        
        rankings = self.get_top_bottom_rankings(n)
        
        for period_name in self.periods.keys():
            if period_name not in rankings:
                continue
            
            print(f"\n{'='*80}")
            print(f"📊 {period_name} LOOKBACK")
            print(f"{'='*80}")
            
            # Top groups
            print(f"\n🟢 TOP INDUSTRY GROUPS - Gaining Shareholders ({period_name})")
            print("-"*80)
            top = rankings[period_name]['top']
            
            for i, (group, row) in enumerate(top.iterrows(), 1):
                print(f"{i:2d}. {group:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):4d} stocks")
            
            # Bottom groups
            print(f"\n🔴 BOTTOM INDUSTRY GROUPS - Losing Shareholders ({period_name})")
            print("-"*80)
            bottom = rankings[period_name]['bottom']
            
            for i, (group, row) in enumerate(bottom.iterrows(), 1):
                print(f"{i:2d}. {group:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):4d} stocks")
    
    def create_comparison_heatmap(self):
        """Create heatmap comparing industry groups across all periods"""
        print("\n📊 Creating comparison heatmap...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to visualize")
            return pd.DataFrame()
        
        # Get first period
        first_period = list(self.period_results.keys())[0]
        
        # Get all groups that appear in all periods
        common_groups = set(self.period_results[first_period].index)
        for period_stats in self.period_results.values():
            common_groups &= set(period_stats.index)
        
        # Build comparison dataframe
        comparison_data = []
        for group in sorted(common_groups):
            row = {'Industry_Group': group}
            for period_name, stats in self.period_results.items():
                row[period_name] = stats.loc[group, 'pct_increasing']
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        comparison_df = comparison_df.set_index('Industry_Group')
        
        if len(comparison_df) == 0:
            print("  ⚠️ No common industry groups across all periods")
            return pd.DataFrame()
        
        # Sort by first period performance
        comparison_df = comparison_df.sort_values(first_period, ascending=False)
        
        # Create heatmap with all groups (since there are fewer groups than industries)
        fig, ax = plt.subplots(figsize=(12, max(8, len(comparison_df) * 0.4)))
        
        sns.heatmap(
            comparison_df,
            annot=True,
            fmt='.1f',
            cmap='RdYlGn',
            center=50,
            vmin=0,
            vmax=100,
            cbar_kws={'label': '% Stocks with Increasing Shareholders'},
            linewidths=0.5,
            ax=ax
        )
        
        ax.set_title('Industry Group Shareholder Growth Comparison Across Time Periods\n' +
                     '(Sorted by 6M Performance)',
                     fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Time Period', fontsize=11, fontweight='bold')
        ax.set_ylabel('Industry Group', fontsize=11, fontweight='bold')
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_group_multi_period_heatmap.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ Heatmap saved: {output_path}")
        
        plt.show()
        
        return comparison_df
    
    def create_period_comparison_chart(self):
        """Create grouped bar chart comparing industry groups across periods"""
        print("\n📊 Creating period comparison chart...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to visualize")
            return
        
        # Get all groups by average performance across all periods
        avg_performance = pd.DataFrame({
            period: stats['pct_increasing'] 
            for period, stats in self.period_results.items()
        })
        
        if len(avg_performance) == 0:
            print("  ⚠️ No performance data to visualize")
            return
        
        avg_performance['avg'] = avg_performance.mean(axis=1)
        all_groups = avg_performance.sort_values('avg', ascending=False).index
        
        # Prepare data for plotting
        plot_data = []
        for group in all_groups:
            for period, stats in self.period_results.items():
                if group in stats.index:
                    plot_data.append({
                        'Industry_Group': group,
                        'Period': period,
                        'Percentage': stats.loc[group, 'pct_increasing']
                    })
        
        plot_df = pd.DataFrame(plot_data)
        
        # Create grouped bar chart
        fig, ax = plt.subplots(figsize=(16, max(8, len(all_groups) * 0.4)))
        
        # Pivot for plotting
        pivot_df = plot_df.pivot(index='Industry_Group', columns='Period', values='Percentage')
        
        # Plot
        pivot_df.plot(kind='barh', ax=ax, width=0.8)
        
        # Add 50% reference line
        ax.axvline(x=50, color='gray', linestyle='--', linewidth=1.5, alpha=0.7, label='50% (Equilibrium)')
        
        ax.set_xlabel('% Stocks with Increasing Shareholders', fontsize=11, fontweight='bold')
        ax.set_ylabel('Industry Group', fontsize=11, fontweight='bold')
        ax.set_title(f'All Industry Groups: Shareholder Growth Across Time Periods',
                     fontsize=14, fontweight='bold', pad=15)
        ax.legend(title='Time Period', loc='lower right', fontsize=9)
        ax.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_path = output_dir / 'industry_group_period_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ Chart saved: {output_path}")
        
        plt.show()
    
    def identify_consistent_performers(self, threshold=60):
        """
        Identify industry groups that consistently show high shareholder growth
        across all time periods
        
        Args:
            threshold: Minimum percentage to be considered "strong growth"
        """
        print(f"\n🎯 Identifying consistent performers (>{threshold}% across all periods)...")
        
        # Check if we have any results
        if not self.period_results or len(self.period_results) == 0:
            print("  ⚠️ No period results available")
            return pd.DataFrame()
        
        # Get first period as base
        first_period = list(self.period_results.keys())[0]
        
        # Build comparison dataframe
        comparison_data = []
        for group in self.period_results[first_period].index:
            row = {'Industry_Group': group}
            all_periods_above_threshold = True
            
            for period_name, stats in self.period_results.items():
                if group in stats.index:
                    pct = stats.loc[group, 'pct_increasing']
                    row[period_name] = pct
                    if pct < threshold:
                        all_periods_above_threshold = False
                else:
                    all_periods_above_threshold = False
            
            row['Consistent'] = all_periods_above_threshold
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) == 0:
            print("  ⚠️ No industry groups to compare")
            return pd.DataFrame()
        
        # Get consistent performers
        consistent = comparison_df[comparison_df['Consistent'] == True].copy()
        
        if len(consistent) > 0:
            consistent['Avg'] = consistent[list(self.periods.keys())].mean(axis=1)
            consistent = consistent.sort_values('Avg', ascending=False)
        
            print(f"\n✅ Found {len(consistent)} industry groups with consistent strong growth:")
            print("-"*80)
            
            for idx, (_, row) in enumerate(consistent.iterrows(), 1):
                print(f"{idx:2d}. {row['Industry_Group']:45s} | Avg: {row['Avg']:5.1f}%")
                for period in self.periods.keys():
                    print(f"    {period:8s}: {row[period]:5.1f}%")
        else:
            print(f"\n⚠️ No industry groups found with >{threshold}% across ALL periods")
            print("    Try lowering the threshold or checking fewer periods")
        
        return consistent
    
    def save_results(self):
        """Save all results to CSV files"""
        print("\n💾 Saving results...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to save")
            return None
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        
        # Save each period separately
        for period_name, stats in self.period_results.items():
            period_clean = period_name.replace(' ', '_').replace('(', '').replace(')', '')
            filename = f'industry_group_shareholders_{period_clean}_{timestamp}.csv'
            output_path = output_dir / filename
            stats.to_csv(output_path)
            print(f"  ✅ Saved: {filename}")
        
        # Get first period as base
        first_period = list(self.period_results.keys())[0]
        
        # Save combined comparison
        comparison_data = []
        for group in self.period_results[first_period].index:
            row = {'Industry_Group': group}
            num_stocks = None
            
            for period_name, stats in self.period_results.items():
                if group in stats.index:
                    row[f'{period_name}_pct'] = stats.loc[group, 'pct_increasing']
                    if num_stocks is None:
                        num_stocks = stats.loc[group, 'num_stocks']
            
            row['num_stocks'] = num_stocks
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) > 0:
            # Sort by first period percentage
            first_period_col = f'{first_period}_pct'
            if first_period_col in comparison_df.columns:
                comparison_df = comparison_df.sort_values(first_period_col, ascending=False)
        
        combined_path = output_dir / f'industry_group_shareholders_all_periods_{timestamp}.csv'
        comparison_df.to_csv(combined_path, index=False)
        print(f"  ✅ Saved combined: industry_group_shareholders_all_periods_{timestamp}.csv")
        
        return combined_path


def main():
    print("="*80)
    print("INDUSTRY GROUP SHAREHOLDER ANALYSIS - MULTI-PERIOD")
    print("Analyzing: 2 Quarters (6M), 1 Year, 2 Years, 5 Years")
    print("="*80)
    
    analyzer = IndustryGroupMultiPeriodAnalyzer()
    
    # Prepare data
    analyzer.prepare_data()
    
    # Analyze all periods
    results = analyzer.analyze_all_periods()
    
    if not results or len(results) == 0:
        print("\n⚠️ No analysis results generated. Check data availability.")
        return analyzer
    
    # Print rankings
    analyzer.print_rankings(n=10)
    
    # Identify consistent performers
    consistent = analyzer.identify_consistent_performers(threshold=60)
    
    # Create visualizations
    comparison_df = analyzer.create_comparison_heatmap()
    analyzer.create_period_comparison_chart()
    
    # Save results
    analyzer.save_results()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
