#!/usr/bin/env python
"""
Market Cap per Shareholder Change Analysis

Calculates the percentage of stocks showing an increase in market cap per shareholder
compared to the previous quarter, and plots this over time.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class ShareholderChangeAnalyzer:
    """Analyze quarter-over-quarter changes in market cap per shareholder"""
    
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
                
                # Map month to quarter end date
                month_map = {
                    'Jan': (1, 31), 'Feb': (2, 28), 'Mar': (3, 31),
                    'Apr': (4, 30), 'May': (5, 31), 'Jun': (6, 30),
                    'Jul': (7, 31), 'Aug': (8, 31), 'Sep': (9, 30),
                    'Oct': (10, 31), 'Nov': (11, 30), 'Dec': (12, 31)
                }
                
                month, day = month_map.get(month_str, (3, 31))
                
                # Handle leap years for February
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
    
    def analyze_qoq_changes(self):
        """
        Calculate percentage of stocks with increasing market cap per shareholder QoQ
        
        Returns:
            DataFrame with columns: quarter_date, pct_increasing, num_compared, total_stocks
        """
        print("\nAnalyzing quarter-over-quarter changes...")
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove rows where date parsing failed
        valid_data = self.shareholding_df.dropna(subset=['quarter_date']).copy()
        
        # Also need valid shareholders and outstanding shares
        valid_data = valid_data[
            (valid_data['total_shareholders'] > 0) & 
            (valid_data['total_outstanding_shares'] > 0)
        ]
        
        print(f"  Processing {len(valid_data):,} valid shareholding records...")
        
        # Get unique quarter dates
        unique_quarters = sorted(valid_data['quarter_date'].unique())
        
        print(f"  Building price lookup and calculating market cap per shareholder...")
        
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
            
            # Vectorized calculation of market cap per shareholder
            merged['market_cap'] = merged['quarter_price'] * merged['total_outstanding_shares']
            merged['market_cap_per_shareholder'] = merged['market_cap'] / merged['total_shareholders']
            
            # Keep only necessary columns
            merged = merged[['isin', 'company_name', 'quarter_date', 'market_cap_per_shareholder']]
            
            all_quarters_data.append(merged)
        
        # Combine all quarters
        print("\n  Combining data from all quarters...")
        all_data = pd.concat(all_quarters_data, ignore_index=True)
        
        # Sort by ISIN and quarter date
        all_data = all_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate previous quarter value for each stock
        print("  Calculating quarter-over-quarter changes...")
        all_data['prev_quarter_value'] = all_data.groupby('isin')['market_cap_per_shareholder'].shift(1)
        all_data['qoq_change'] = all_data['market_cap_per_shareholder'] - all_data['prev_quarter_value']
        all_data['is_increase'] = all_data['qoq_change'] > 0
        
        # Group by quarter and calculate percentage increasing
        results = []
        
        for quarter_date in sorted(unique_quarters[1:]):  # Skip first quarter (no previous data)
            quarter_data = all_data[all_data['quarter_date'] == quarter_date]
            
            # Only consider stocks where we have previous quarter data
            comparable = quarter_data.dropna(subset=['prev_quarter_value'])
            
            if len(comparable) > 0:
                pct_increasing = (comparable['is_increase'].sum() / len(comparable)) * 100
                
                results.append({
                    'quarter_date': quarter_date,
                    'pct_increasing': pct_increasing,
                    'num_increasing': comparable['is_increase'].sum(),
                    'num_decreasing': (~comparable['is_increase']).sum(),
                    'num_compared': len(comparable),
                    'total_stocks': len(quarter_data)
                })
        
        results_df = pd.DataFrame(results)
        
        print(f"\n✅ Calculated QoQ changes for {len(results_df)} quarters")
        
        return results_df
    
    def plot_results(self, results_df, save_path=None):
        """Plot the percentage of stocks with increasing market cap per shareholder"""
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Plot 1: Percentage of stocks showing increase
        ax1.plot(results_df['quarter_date'], results_df['pct_increasing'],
                linewidth=2.5,
                marker='o',
                markersize=7,
                color='#2E86AB',
                label='% Stocks Increasing')
        
        # Add 50% reference line
        ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5, linewidth=1.5, label='50% (Equilibrium)')
        
        # Shade above/below 50%
        ax1.fill_between(results_df['quarter_date'], 50, results_df['pct_increasing'],
                         where=(results_df['pct_increasing'] >= 50),
                         alpha=0.3, color='green', label='Majority Increasing')
        ax1.fill_between(results_df['quarter_date'], 50, results_df['pct_increasing'],
                         where=(results_df['pct_increasing'] < 50),
                         alpha=0.3, color='red', label='Majority Decreasing')
        
        ax1.set_xlabel('Quarter', fontsize=11, fontweight='bold')
        ax1.set_ylabel('% of Stocks with Increasing Value', fontsize=11, fontweight='bold')
        ax1.set_title('Shareholding Concentration Trend: % of Stocks with Increasing Market Cap per Shareholder (QoQ)',
                     fontsize=13, fontweight='bold', pad=15)
        ax1.set_ylim(0, 100)
        ax1.legend(loc='best', fontsize=10, framealpha=0.9)
        ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Plot 2: Number of stocks compared
        ax2.bar(results_df['quarter_date'], results_df['num_compared'],
                color='#2ca02c',
                alpha=0.7,
                edgecolor='black',
                linewidth=0.5)
        
        ax2.set_xlabel('Quarter', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Number of Stocks Compared', fontsize=11, fontweight='bold')
        ax2.set_title('Number of Stocks with Quarter-over-Quarter Comparison Data',
                     fontsize=13, fontweight='bold', pad=15)
        ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, axis='y')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Save plot
        if save_path is None:
            output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
            output_dir.mkdir(parents=True, exist_ok=True)
            save_path = output_dir / 'shareholding_qoq_change_analysis_plot.png'
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Plot saved to: {save_path}")
        
        plt.show()
    
    def save_results(self, results_df, filename=None):
        """Save results to CSV"""
        if filename is None:
            filename = 'shareholding_qoq_change_analysis.csv'
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        results_df.to_csv(output_path, index=False)
        
        print(f"\n✅ Results saved to: {output_path}")
        return output_path


def main():
    """Main execution"""
    print("="*80)
    print("SHAREHOLDING CONCENTRATION CHANGE ANALYSIS (QoQ)")
    print("="*80)
    
    analyzer = ShareholderChangeAnalyzer()
    
    # Analyze QoQ changes
    results_df = analyzer.analyze_qoq_changes()
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nAnalysis Period: {results_df['quarter_date'].min().date()} to {results_df['quarter_date'].max().date()}")
    print(f"Total Quarters Analyzed: {len(results_df)}")
    
    print(f"\nPercentage of Stocks with Increasing Market Cap per Shareholder:")
    print(f"  Average: {results_df['pct_increasing'].mean():.1f}%")
    print(f"  Median:  {results_df['pct_increasing'].median():.1f}%")
    print(f"  Min:     {results_df['pct_increasing'].min():.1f}% ({results_df[results_df['pct_increasing'] == results_df['pct_increasing'].min()]['quarter_date'].values[0]})")
    print(f"  Max:     {results_df['pct_increasing'].max():.1f}% ({results_df[results_df['pct_increasing'] == results_df['pct_increasing'].max()]['quarter_date'].values[0]})")
    
    # Count quarters above/below 50%
    above_50 = (results_df['pct_increasing'] >= 50).sum()
    below_50 = (results_df['pct_increasing'] < 50).sum()
    print(f"\nQuarters with majority increasing: {above_50} ({above_50/len(results_df)*100:.1f}%)")
    print(f"Quarters with majority decreasing: {below_50} ({below_50/len(results_df)*100:.1f}%)")
    
    # Show recent trend
    print("\nRecent Values (Last 10 quarters):")
    print("-"*80)
    for _, row in results_df.tail(10).iterrows():
        direction = "↑" if row['pct_increasing'] >= 50 else "↓"
        print(f"{row['quarter_date'].date()}  |  {row['pct_increasing']:>5.1f}% {direction}  |  ({row['num_increasing']:>4.0f} ↑ / {row['num_decreasing']:>4.0f} ↓ / {row['num_compared']:>4.0f} total)")
    
    print("="*80)
    
    # Save results
    output_path = analyzer.save_results(results_df)
    
    # Plot results
    analyzer.plot_results(results_df)
    
    return results_df


if __name__ == "__main__":
    results_df = main()
