#!/usr/bin/env python
"""
Combined Shareholding Analysis Plot - 1 Year (4 Quarter) Changes

Plots both:
1. % of stocks with increasing market cap per shareholder (over 4 quarters/1 year)
2. % of stocks with increasing number of shareholders (over 4 quarters/1 year)

on the same chart for comparison.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class OneYearChangeAnalyzer:
    """Analyze 1-year (4 quarter) changes in shareholding patterns"""
    
    def __init__(self, base_path=None):
        """Initialize the analyzer"""
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading data...")
        self._load_data()
        
    def _load_data(self):
        """Load shareholding patterns and price data"""
        # Load shareholding patterns
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders', 'total_outstanding_shares']
        )
        
        # Load price data with optimized types
        self.price_df = pd.read_csv(
            self.database_path / 'price_data.csv',
            parse_dates=['date'],
            usecols=['isin', 'date', 'close'],
            dtype={'isin': 'category', 'close': 'float32'}
        )
        
        # Sort for efficient lookups
        self.price_df = self.price_df.sort_values(['isin', 'date'])
        
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
        print(f"Loaded {len(self.price_df):,} price records")
        
    def _parse_quarter_to_date(self, quarter_str):
        """Convert quarter strings to quarter-end dates"""
        quarter_str = str(quarter_str).strip()
        
        try:
            # Handle 'Mon-YYYY' format
            if '-' in quarter_str and len(quarter_str.split('-')) == 2:
                month_str, year_str = quarter_str.split('-')
                year = int(year_str)
                
                month_map = {
                    'Jan': (1, 31), 'Feb': (2, 28), 'Mar': (3, 31),
                    'Apr': (4, 30), 'May': (5, 31), 'Jun': (6, 30),
                    'Jul': (7, 31), 'Aug': (8, 31), 'Sep': (9, 30),
                    'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31)
                }
                
                month, day = month_map.get(month_str, (3, 31))
                
                if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    day = 29
                
                return pd.Timestamp(year=year, month=month, day=day)
            
            # Handle 'Q# FY####' format
            elif 'Q' in quarter_str and 'FY' in quarter_str:
                parts = quarter_str.replace('FY', '').split('Q')
                quarter_num = int(parts[1].split()[0])
                fy_year = int(parts[1].split()[1])
                
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
            print(f"Warning: Could not parse quarter '{quarter_str}': {e}")
            return None
    
    def analyze_one_year_changes(self):
        """
        Calculate 1-year (4 quarter) changes for both metrics
        
        Returns:
            DataFrame with both metrics
        """
        print("\nAnalyzing 1-year (4 quarter) changes...")
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove rows where date parsing failed
        valid_data = self.shareholding_df.dropna(subset=['quarter_date']).copy()
        
        # Need valid data
        valid_data = valid_data[
            (valid_data['total_shareholders'] > 0) & 
            (valid_data['total_outstanding_shares'] > 0)
        ]
        
        print(f"  Processing {len(valid_data):,} valid shareholding records...")
        
        # Get unique quarter dates
        unique_quarters = sorted(valid_data['quarter_date'].unique())
        
        print(f"  Calculating market cap per shareholder for all quarters...")
        
        # Calculate market cap per shareholder for all quarters
        all_quarters_data = []
        
        for i, quarter_date in enumerate(unique_quarters, 1):
            if i % 5 == 0:
                print(f"    Processing quarter {i}/{len(unique_quarters)}: {quarter_date.date()}")
            
            # Get stocks for this quarter
            quarter_stocks = valid_data[valid_data['quarter_date'] == quarter_date].copy()
            
            # Get prices within +/- 10 days of quarter end
            date_min = quarter_date - pd.Timedelta(days=10)
            date_max = quarter_date + pd.Timedelta(days=10)
            
            relevant_prices = self.price_df[
                (self.price_df['date'] >= date_min) & 
                (self.price_df['date'] <= date_max)
            ].copy()
            
            # Calculate date difference
            relevant_prices['date_diff'] = abs((relevant_prices['date'] - quarter_date).dt.days)
            
            # Get closest price for each ISIN (vectorized)
            if len(relevant_prices) > 0:
                closest_prices = relevant_prices.loc[
                    relevant_prices.groupby('isin', observed=True)['date_diff'].idxmin()
                ][['isin', 'close']].rename(columns={'close': 'quarter_price'})
            else:
                continue
            
            # Merge with shareholding data
            merged = quarter_stocks.merge(closest_prices, on='isin', how='inner')
            
            # Vectorized calculation
            merged['market_cap'] = merged['quarter_price'] * merged['total_outstanding_shares']
            merged['market_cap_per_shareholder'] = merged['market_cap'] / merged['total_shareholders']
            
            # Keep necessary columns
            merged = merged[['isin', 'company_name', 'quarter_date', 'total_shareholders', 'market_cap_per_shareholder']]
            
            all_quarters_data.append(merged)
        
        # Combine all quarters
        print("\n  Combining data and calculating 1-year (4Q) changes...")
        all_data = pd.concat(all_quarters_data, ignore_index=True)
        
        # Sort by ISIN and quarter date
        all_data = all_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate values 4 quarters ago using shift(4)
        all_data['prev_4q_shareholders'] = all_data.groupby('isin')['total_shareholders'].shift(4)
        all_data['prev_4q_mcap_per_sh'] = all_data.groupby('isin')['market_cap_per_shareholder'].shift(4)
        
        # Calculate changes
        all_data['shareholders_4q_change'] = all_data['total_shareholders'] - all_data['prev_4q_shareholders']
        all_data['mcap_per_sh_4q_change'] = all_data['market_cap_per_shareholder'] - all_data['prev_4q_mcap_per_sh']
        
        # Calculate percentage changes for analysis
        all_data['shareholders_4q_pct_change'] = (all_data['shareholders_4q_change'] / all_data['prev_4q_shareholders']) * 100
        all_data['mcap_per_sh_4q_pct_change'] = (all_data['mcap_per_sh_4q_change'] / all_data['prev_4q_mcap_per_sh']) * 100
        
        # Determine if increasing
        all_data['shareholders_increasing'] = all_data['shareholders_4q_change'] > 0
        all_data['mcap_per_sh_increasing'] = all_data['mcap_per_sh_4q_change'] > 0
        
        # Group by quarter and calculate percentages
        results = []
        
        for quarter_date in sorted(unique_quarters[4:]):  # Skip first 4 quarters (no 1-year-ago data)
            quarter_data = all_data[all_data['quarter_date'] == quarter_date]
            
            # Only consider stocks where we have 1-year-ago data
            comparable = quarter_data.dropna(subset=['prev_4q_shareholders', 'prev_4q_mcap_per_sh'])
            
            if len(comparable) > 0:
                pct_shareholders_inc = (comparable['shareholders_increasing'].sum() / len(comparable)) * 100
                pct_mcap_per_sh_inc = (comparable['mcap_per_sh_increasing'].sum() / len(comparable)) * 100
                
                results.append({
                    'quarter_date': quarter_date,
                    'pct_shareholders_increasing': pct_shareholders_inc,
                    'pct_mcap_per_sh_increasing': pct_mcap_per_sh_inc,
                    'num_shareholders_inc': comparable['shareholders_increasing'].sum(),
                    'num_mcap_per_sh_inc': comparable['mcap_per_sh_increasing'].sum(),
                    'num_compared': len(comparable),
                    'avg_shareholders_change': comparable['shareholders_4q_change'].mean(),
                    'avg_mcap_per_sh_change': comparable['mcap_per_sh_4q_change'].mean(),
                    'median_shareholders_pct_change': comparable['shareholders_4q_pct_change'].median(),
                    'median_mcap_per_sh_pct_change': comparable['mcap_per_sh_4q_pct_change'].median()
                })
        
        results_df = pd.DataFrame(results)
        
        print(f"\n✅ Calculated 1-year changes for {len(results_df)} quarters")
        
        return results_df
    
    def plot_results(self, results_df):
        """Plot the combined 1-year analysis"""
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12))
        
        # Plot 1: Both metrics on same chart
        ax1.plot(results_df['quarter_date'], results_df['pct_mcap_per_sh_increasing'],
                linewidth=2.5,
                marker='o',
                markersize=6,
                color='#2E86AB',
                label='% Stocks: Increasing Market Cap per Shareholder (1Y)',
                alpha=0.8)
        
        ax1.plot(results_df['quarter_date'], results_df['pct_shareholders_increasing'],
                linewidth=2.5,
                marker='s',
                markersize=6,
                color='#E63946',
                label='% Stocks: Increasing Number of Shareholders (1Y)',
                alpha=0.8)
        
        # Add 50% reference line
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, linewidth=1.5, label='50% (Equilibrium)')
        
        ax1.set_xlabel('Quarter', fontsize=11, fontweight='bold')
        ax1.set_ylabel('% of Stocks', fontsize=11, fontweight='bold')
        ax1.set_title('Shareholding Pattern Comparison (1-Year Changes): Market Cap per Shareholder vs Number of Shareholders',
                     fontsize=13, fontweight='bold', pad=15)
        ax1.set_ylim(0, 100)
        ax1.legend(loc='best', fontsize=10, framealpha=0.9)
        ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Plot 2: Difference between the two metrics
        results_df['difference'] = results_df['pct_mcap_per_sh_increasing'] - results_df['pct_shareholders_increasing']
        
        colors = ['green' if x >= 0 else 'red' for x in results_df['difference']]
        ax2.bar(results_df['quarter_date'], results_df['difference'],
               color=colors,
               alpha=0.7,
               edgecolor='black',
               linewidth=0.5)
        
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=1.5)
        ax2.set_xlabel('Quarter', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Difference (% points)', fontsize=11, fontweight='bold')
        ax2.set_title('Concentration vs Participation (1Y Change): Difference Between Metrics\n(Positive = More concentration, Negative = More participation)',
                     fontsize=13, fontweight='bold', pad=15)
        ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='y')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add annotation
        ax2.text(0.02, 0.97, 
                 'Green: Wealth concentrating (fewer but wealthier shareholders over 1Y)\n'
                 'Red: Broader participation (more shareholders joining over 1Y)',
                 transform=ax2.transAxes,
                 fontsize=9,
                 verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Plot 3: Correlation scatter plot (all data points)
        ax3.scatter(results_df['pct_shareholders_increasing'], results_df['pct_mcap_per_sh_increasing'],
                   s=100,
                   alpha=0.6,
                   c=range(len(results_df)),
                   cmap='viridis',
                   edgecolors='black',
                   linewidth=1)
        
        # Add trend line
        z = np.polyfit(results_df['pct_shareholders_increasing'], results_df['pct_mcap_per_sh_increasing'], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(results_df['pct_shareholders_increasing'].min(), 
                             results_df['pct_shareholders_increasing'].max(), 100)
        ax3.plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2, label=f'Trend: y={z[0]:.2f}x+{z[1]:.2f}')
        
        # Add reference lines
        ax3.axhline(y=50, color='gray', linestyle='--', alpha=0.3, linewidth=1)
        ax3.axvline(x=50, color='gray', linestyle='--', alpha=0.3, linewidth=1)
        
        ax3.set_xlabel('% Stocks: Increasing Number of Shareholders (1Y)', fontsize=11, fontweight='bold')
        ax3.set_ylabel('% Stocks: Increasing Market Cap per Shareholder (1Y)', fontsize=11, fontweight='bold')
        ax3.set_title('Correlation Analysis (1Y Changes, All Data)\nDarker points = More recent',
                     fontsize=13, fontweight='bold', pad=15)
        ax3.set_xlim(0, 100)
        ax3.set_ylim(0, 100)
        ax3.legend(loc='best', fontsize=9)
        ax3.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        
        # Add quadrant labels
        ax3.text(75, 75, 'Both\nIncreasing', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
        ax3.text(25, 75, 'Concentration\nWithout Growth', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
        ax3.text(75, 25, 'Participation\nWithout Value', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
        ax3.text(25, 25, 'Both\nDecreasing', ha='center', va='center', fontsize=9, alpha=0.5, weight='bold')
        
        plt.tight_layout()
        
        # Save plot
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'combined_shareholding_1y_change_analysis_plot.png'
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Plot saved to: {output_path}")
        
        plt.show()
    
    def save_results(self, results_df):
        """Save results to CSV"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / 'combined_shareholding_1y_change_analysis.csv'
        results_df.to_csv(output_path, index=False)
        
        print(f"\n✅ Results saved to: {output_path}")
        return output_path


def main():
    """Main execution"""
    print("="*80)
    print("COMBINED SHAREHOLDING ANALYSIS - 1 YEAR (4 QUARTER) CHANGES")
    print("="*80)
    
    analyzer = OneYearChangeAnalyzer()
    
    # Analyze 1-year changes
    results_df = analyzer.analyze_one_year_changes()
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nAnalysis Period: {results_df['quarter_date'].min().date()} to {results_df['quarter_date'].max().date()}")
    print(f"Total Quarters Analyzed: {len(results_df)}")
    
    print(f"\nMarket Cap per Shareholder (1Y Change):")
    print(f"  Average: {results_df['pct_mcap_per_sh_increasing'].mean():.1f}%")
    print(f"  Median:  {results_df['pct_mcap_per_sh_increasing'].median():.1f}%")
    print(f"  Min:     {results_df['pct_mcap_per_sh_increasing'].min():.1f}%")
    print(f"  Max:     {results_df['pct_mcap_per_sh_increasing'].max():.1f}%")
    
    print(f"\nNumber of Shareholders (1Y Change):")
    print(f"  Average: {results_df['pct_shareholders_increasing'].mean():.1f}%")
    print(f"  Median:  {results_df['pct_shareholders_increasing'].median():.1f}%")
    print(f"  Min:     {results_df['pct_shareholders_increasing'].min():.1f}%")
    print(f"  Max:     {results_df['pct_shareholders_increasing'].max():.1f}%")
    
    # Difference stats
    results_df['difference'] = results_df['pct_mcap_per_sh_increasing'] - results_df['pct_shareholders_increasing']
    print(f"\nDifference (Concentration - Participation):")
    print(f"  Average: {results_df['difference'].mean():.1f} percentage points")
    print(f"  Median:  {results_df['difference'].median():.1f} percentage points")
    
    # Correlation
    correlation = results_df['pct_mcap_per_sh_increasing'].corr(results_df['pct_shareholders_increasing'])
    print(f"\nCorrelation between metrics: {correlation:.3f}")
    
    if correlation > 0.5:
        print("  → Strong positive correlation: Both metrics move together")
    elif correlation > 0:
        print("  → Weak positive correlation: Some tendency to move together")
    elif correlation > -0.5:
        print("  → Weak negative correlation: Some tendency to move opposite")
    else:
        print("  → Strong negative correlation: Metrics move in opposite directions")
    
    # Recent trend
    print("\nRecent Values (Last 10 quarters):")
    print("-"*80)
    print(f"{'Quarter':<12} | {'MCap/SH %':>10} | {'#SH %':>10} | {'Difference':>12}")
    print("-"*80)
    for _, row in results_df.tail(10).iterrows():
        diff_sign = "+" if row['difference'] >= 0 else ""
        print(f"{row['quarter_date'].date()} | {row['pct_mcap_per_sh_increasing']:>9.1f}% | {row['pct_shareholders_increasing']:>9.1f}% | {diff_sign}{row['difference']:>10.1f} pts")
    
    print("="*80)
    
    # Save results
    analyzer.save_results(results_df)
    
    # Plot results
    analyzer.plot_results(results_df)
    
    return results_df


if __name__ == "__main__":
    results_df = main()
