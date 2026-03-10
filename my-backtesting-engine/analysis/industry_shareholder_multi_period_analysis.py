#!/usr/bin/env python
"""
Industry Shareholder Analysis - Multi-Period (2Q, 1Y, 2Y, 5Y)

Analyzes which industries are gaining/losing shareholders across different time horizons:
- 2 Quarters (6 months)
- 1 Year (4 quarters)
- 2 Years (8 quarters)
- 5 Years (20 quarters)

Purpose: Identify industries with sustained shareholder growth patterns
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class IndustryMultiPeriodAnalyzer:
    """Analyze industry shareholder changes across multiple time periods"""
    
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
        
        # Industry info
        self.industry_df = pd.read_csv(
            self.database_path / 'industry_info.csv',
            usecols=['isin', 'industry']
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
        """Prepare data with industry mapping and quarter dates"""
        print("\nPreparing data...")
        
        # Merge with industry
        df = self.shareholding_df.merge(
            self.industry_df,
            on='isin',
            how='left'
        )
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        df['quarter_date'] = df['quarter'].apply(self._parse_quarter_to_date)
        
        # Remove invalid data
        df = df.dropna(subset=['quarter_date', 'total_shareholders', 'industry'])
        df = df[df['total_shareholders'] > 0]
        df = df[df['industry'] != 'Not Available']
        
        # Sort
        df = df.sort_values(['isin', 'quarter_date'])
        
        print(f"  Valid records: {len(df):,}")
        print(f"  Industries: {df['industry'].nunique()}")
        print(f"  Date range: {df['quarter_date'].min().date()} to {df['quarter_date'].max().date()}")
        
        self.prepared_df = df
        
        return df
    
    def analyze_period(self, quarters_back):
        """
        Analyze shareholder changes for a specific lookback period
        
        Args:
            quarters_back: Number of quarters to look back (2, 4, 8, 20)
        
        Returns:
            DataFrame with industry rankings for this period
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
        
        # Calculate by industry
        industry_stats = latest_data.groupby('industry').agg({
            'isin': 'count',
            f'is_increase_{quarters_back}q': ['sum', 'mean'],
            f'change_{quarters_back}q': ['mean', 'median']
        }).round(4)
        
        # Flatten column names
        industry_stats.columns = ['num_stocks', 'num_increasing', 'pct_increasing', 'avg_change', 'median_change']
        industry_stats['pct_increasing'] = industry_stats['pct_increasing'] * 100
        
        # Sort by percentage increasing
        industry_stats = industry_stats.sort_values('pct_increasing', ascending=False)
        
        # Filter out industries with too few stocks
        industry_stats = industry_stats[industry_stats['num_stocks'] >= 5]
        
        print(f"    ✅ Analyzed {len(industry_stats)} industries")
        print(f"    Latest quarter: {latest_quarter.date()}")
        print(f"    Stocks with data: {len(latest_data)}")
        
        return industry_stats
    
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
        """Get top and bottom N industries for each period"""
        rankings = {}
        
        for period_name, stats in self.period_results.items():
            rankings[period_name] = {
                'top': stats.head(n),
                'bottom': stats.tail(n)[::-1]  # Reverse order for bottom
            }
        
        return rankings
    
    def print_rankings(self, n=10):
        """Print formatted rankings for all periods"""
        print("\n" + "="*80)
        print("INDUSTRY RANKINGS - MULTI-PERIOD ANALYSIS")
        print("="*80)
        
        rankings = self.get_top_bottom_rankings(n)
        
        for period_name in self.periods.keys():
            if period_name not in rankings:
                continue
            
            print(f"\n{'='*80}")
            print(f"📊 {period_name} LOOKBACK")
            print(f"{'='*80}")
            
            # Top industries
            print(f"\n🟢 TOP {n} INDUSTRIES - Gaining Shareholders ({period_name})")
            print("-"*80)
            top = rankings[period_name]['top']
            
            for i, (industry, row) in enumerate(top.iterrows(), 1):
                print(f"{i:2d}. {industry:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):3d} stocks")
            
            # Bottom industries
            print(f"\n🔴 BOTTOM {n} INDUSTRIES - Losing Shareholders ({period_name})")
            print("-"*80)
            bottom = rankings[period_name]['bottom']
            
            for i, (industry, row) in enumerate(bottom.iterrows(), 1):
                print(f"{i:2d}. {industry:45s} | {row['pct_increasing']:5.1f}% | "
                      f"{int(row['num_stocks']):3d} stocks")
    
    def create_comparison_heatmap(self):
        """Create heatmap comparing industries across all periods"""
        print("\n📊 Creating comparison heatmap...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to visualize")
            return pd.DataFrame()
        
        # Get first period
        first_period = list(self.period_results.keys())[0]
        
        # Get all industries that appear in all periods
        common_industries = set(self.period_results[first_period].index)
        for period_stats in self.period_results.values():
            common_industries &= set(period_stats.index)
        
        # Build comparison dataframe
        comparison_data = []
        for industry in sorted(common_industries):
            row = {'Industry': industry}
            for period_name, stats in self.period_results.items():
                row[period_name] = stats.loc[industry, 'pct_increasing']
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        comparison_df = comparison_df.set_index('Industry')
        
        if len(comparison_df) == 0:
            print("  ⚠️ No common industries across all periods")
            return pd.DataFrame()
        
        # Sort by first period performance
        comparison_df = comparison_df.sort_values(first_period, ascending=False)
        
        # Take top 30 for visualization
        top_industries = comparison_df.head(15)
        bottom_industries = comparison_df.tail(15)
        viz_df = pd.concat([top_industries, bottom_industries])
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(12, 14))
        
        sns.heatmap(
            viz_df,
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
        
        ax.set_title('Industry Shareholder Growth Comparison Across Time Periods\n' +
                     'Top 15 & Bottom 15 Industries (Sorted by 6M Performance)',
                     fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Time Period', fontsize=11, fontweight='bold')
        ax.set_ylabel('Industry', fontsize=11, fontweight='bold')
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'industry_multi_period_heatmap.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ Heatmap saved: {output_path}")
        
        plt.show()
        
        return comparison_df
    
    def create_period_comparison_chart(self, top_n=15):
        """Create grouped bar chart comparing top industries across periods"""
        print("\n📊 Creating period comparison chart...")
        
        if not hasattr(self, 'period_results') or len(self.period_results) == 0:
            print("  ⚠️ No results to visualize")
            return
        
        # Get top N industries by average performance across all periods
        avg_performance = pd.DataFrame({
            period: stats['pct_increasing'] 
            for period, stats in self.period_results.items()
        })
        
        if len(avg_performance) == 0:
            print("  ⚠️ No performance data to visualize")
            return
        avg_performance['avg'] = avg_performance.mean(axis=1)
        top_industries = avg_performance.nlargest(top_n, 'avg').index
        
        # Prepare data for plotting
        plot_data = []
        for industry in top_industries:
            for period, stats in self.period_results.items():
                if industry in stats.index:
                    plot_data.append({
                        'Industry': industry[:30] + '...' if len(industry) > 30 else industry,
                        'Period': period,
                        'Percentage': stats.loc[industry, 'pct_increasing']
                    })
        
        plot_df = pd.DataFrame(plot_data)
        
        # Create grouped bar chart
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Pivot for plotting
        pivot_df = plot_df.pivot(index='Industry', columns='Period', values='Percentage')
        
        # Plot
        pivot_df.plot(kind='barh', ax=ax, width=0.8)
        
        # Add 50% reference line
        ax.axvline(x=50, color='gray', linestyle='--', linewidth=1.5, alpha=0.7, label='50% (Equilibrium)')
        
        ax.set_xlabel('% Stocks with Increasing Shareholders', fontsize=11, fontweight='bold')
        ax.set_ylabel('Industry', fontsize=11, fontweight='bold')
        ax.set_title(f'Top {top_n} Industries: Shareholder Growth Across Time Periods',
                     fontsize=14, fontweight='bold', pad=15)
        ax.legend(title='Time Period', loc='lower right', fontsize=9)
        ax.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_path = output_dir / 'industry_period_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  ✅ Chart saved: {output_path}")
        
        plt.show()
    
    def identify_consistent_performers(self, threshold=60):
        """
        Identify industries that consistently show high shareholder growth
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
        for industry in self.period_results[first_period].index:
            row = {'Industry': industry}
            all_periods_above_threshold = True
            
            for period_name, stats in self.period_results.items():
                if industry in stats.index:
                    pct = stats.loc[industry, 'pct_increasing']
                    row[period_name] = pct
                    if pct < threshold:
                        all_periods_above_threshold = False
                else:
                    all_periods_above_threshold = False
            
            row['Consistent'] = all_periods_above_threshold
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) == 0:
            print("  ⚠️ No industries to compare")
            return pd.DataFrame()
        
        # Get consistent performers
        consistent = comparison_df[comparison_df['Consistent'] == True].copy()
        
        if len(consistent) > 0:
            consistent['Avg'] = consistent[list(self.periods.keys())].mean(axis=1)
            consistent = consistent.sort_values('Avg', ascending=False)
        
        if len(consistent) > 0:
            print(f"\n✅ Found {len(consistent)} industries with consistent strong growth:")
            print("-"*80)
            
            for idx, (_, row) in enumerate(consistent.iterrows(), 1):
                print(f"{idx:2d}. {row['Industry']:45s} | Avg: {row['Avg']:5.1f}%")
                for period in self.periods.keys():
                    print(f"    {period:8s}: {row[period]:5.1f}%")
        else:
            print(f"\n⚠️ No industries found with >{threshold}% across ALL periods")
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
            filename = f'industry_shareholders_{period_clean}_{timestamp}.csv'
            output_path = output_dir / filename
            stats.to_csv(output_path)
            print(f"  ✅ Saved: {filename}")
        
        # Get first period as base
        first_period = list(self.period_results.keys())[0]
        
        # Save combined comparison
        comparison_data = []
        for industry in self.period_results[first_period].index:
            row = {'Industry': industry}
            num_stocks = None
            
            for period_name, stats in self.period_results.items():
                if industry in stats.index:
                    row[f'{period_name}_pct'] = stats.loc[industry, 'pct_increasing']
                    if num_stocks is None:
                        num_stocks = stats.loc[industry, 'num_stocks']
            
            row['num_stocks'] = num_stocks
            comparison_data.append(row)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        if len(comparison_df) > 0:
            # Sort by first period percentage
            first_period_col = f'{first_period}_pct'
            if first_period_col in comparison_df.columns:
                comparison_df = comparison_df.sort_values(first_period_col, ascending=False)
        
        combined_path = output_dir / f'industry_shareholders_all_periods_{timestamp}.csv'
        comparison_df.to_csv(combined_path, index=False)
        print(f"  ✅ Saved combined: industry_shareholders_all_periods_{timestamp}.csv")
        
        return combined_path


def main():
    print("="*80)
    print("INDUSTRY SHAREHOLDER ANALYSIS - MULTI-PERIOD")
    print("Analyzing: 2 Quarters (6M), 1 Year, 2 Years, 5 Years")
    print("="*80)
    
    analyzer = IndustryMultiPeriodAnalyzer()
    
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
    analyzer.create_period_comparison_chart(top_n=15)
    
    # Save results
    analyzer.save_results()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    
    return analyzer


if __name__ == "__main__":
    analyzer = main()
