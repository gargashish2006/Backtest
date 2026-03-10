#!/usr/bin/env python
"""
Shareholder Count Increase Analysis - 2 Quarter (6 Month) Period

Calculates the percentage of stocks showing an increase in number of shareholders
compared to 2 quarters (6 months) ago.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ShareholderTwoQuarterAnalyzer:
    """Analyze 2-quarter changes in shareholder count"""
    
    def __init__(self, base_path=None):
        if base_path is None:
            base_path = Path(__file__).parent.parent
        else:
            base_path = Path(base_path)
        
        self.base_path = base_path
        self.database_path = base_path / 'database'
        
        print("Loading shareholding data...")
        self._load_data()
    
    def _load_data(self):
        """Load shareholding patterns"""
        self.shareholding_df = pd.read_csv(
            self.database_path / 'shareholding_patterns.csv',
            usecols=['isin', 'company_name', 'quarter', 'total_shareholders']
        )
        print(f"Loaded {len(self.shareholding_df):,} shareholding records")
    
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
    
    def analyze_2q_shareholder_changes(self):
        """
        Calculate percentage of stocks with increasing shareholder count 
        compared to 2 quarters ago
        """
        print("\nAnalyzing 2-quarter shareholder count changes...")
        
        # Parse quarter dates
        print("  Parsing quarter dates...")
        self.shareholding_df['quarter_date'] = self.shareholding_df['quarter'].apply(
            self._parse_quarter_to_date
        )
        
        # Remove invalid data
        valid_data = self.shareholding_df.dropna(subset=['quarter_date', 'total_shareholders']).copy()
        valid_data = valid_data[valid_data['total_shareholders'] > 0]
        
        print(f"  Processing {len(valid_data):,} valid records...")
        
        # Sort by ISIN and quarter date
        valid_data = valid_data.sort_values(['isin', 'quarter_date'])
        
        # Calculate shareholder count 2 quarters ago
        valid_data['shareholders_2q_ago'] = valid_data.groupby('isin')['total_shareholders'].shift(2)
        valid_data['change_2q'] = valid_data['total_shareholders'] - valid_data['shareholders_2q_ago']
        valid_data['is_increase'] = valid_data['change_2q'] > 0
        
        # Get unique quarters
        unique_quarters = sorted(valid_data['quarter_date'].unique())
        
        # Calculate percentage for each quarter
        results = []
        
        for quarter_date in sorted(unique_quarters[2:]):  # Skip first 2 quarters
            quarter_data = valid_data[valid_data['quarter_date'] == quarter_date]
            
            # Only stocks with 2Q-ago data
            comparable = quarter_data.dropna(subset=['shareholders_2q_ago'])
            
            if len(comparable) > 0:
                pct_increasing = (comparable['is_increase'].sum() / len(comparable)) * 100
                
                results.append({
                    'quarter_date': quarter_date,
                    'pct_increasing': pct_increasing,
                    'num_increasing': comparable['is_increase'].sum(),
                    'num_decreasing': (~comparable['is_increase']).sum(),
                    'num_compared': len(comparable),
                    'avg_change': comparable['change_2q'].mean(),
                    'median_change': comparable['change_2q'].median()
                })
        
        results_df = pd.DataFrame(results)
        
        print(f"\n✅ Analyzed {len(results_df)} quarters")
        
        return results_df
    
    def plot_results(self, results_df):
        """Plot the 2-quarter shareholder increase trend"""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.plot(results_df['quarter_date'], results_df['pct_increasing'],
                linewidth=2.5, marker='o', markersize=7, color='#E63946',
                label='% Stocks with Increased Shareholders (vs 2Q ago)')
        
        # 50% reference line
        ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, 
                   linewidth=1.5, label='50% (Equilibrium)')
        
        # Shade regions
        ax.fill_between(results_df['quarter_date'], 50, results_df['pct_increasing'],
                        where=(results_df['pct_increasing'] >= 50),
                        alpha=0.3, color='green', label='Majority Increasing')
        ax.fill_between(results_df['quarter_date'], 50, results_df['pct_increasing'],
                        where=(results_df['pct_increasing'] < 50),
                        alpha=0.3, color='red', label='Majority Decreasing')
        
        ax.set_xlabel('Quarter', fontsize=11, fontweight='bold')
        ax.set_ylabel('% of Stocks', fontsize=11, fontweight='bold')
        ax.set_title('Shareholder Base Expansion: % Stocks with Increased Shareholders (6-Month Period)',
                     fontsize=13, fontweight='bold', pad=15)
        ax.set_ylim(0, 100)
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save
        output_dir = self.base_path / 'analysis' / 'outputs' / 'charts'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / 'shareholder_2q_increase.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"\n📊 Chart saved: {output_path}")
        
        plt.show()
    
    def save_results(self, results_df):
        """Save results to CSV"""
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = output_dir / f'shareholder_2q_increase_{timestamp}.csv'
        
        results_df.to_csv(output_path, index=False)
        print(f"✅ Results saved: {output_path}")
        
        return output_path


def main():
    print("="*80)
    print("SHAREHOLDER COUNT INCREASE ANALYSIS - 2 QUARTERS (6 MONTHS)")
    print("="*80)
    
    analyzer = ShareholderTwoQuarterAnalyzer()
    
    # Analyze
    results_df = analyzer.analyze_2q_shareholder_changes()
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nPeriod: {results_df['quarter_date'].min().date()} to {results_df['quarter_date'].max().date()}")
    print(f"Quarters Analyzed: {len(results_df)}")
    
    print(f"\n% Stocks with Increased Shareholders (vs 2Q ago):")
    print(f"  Average: {results_df['pct_increasing'].mean():.1f}%")
    print(f"  Median:  {results_df['pct_increasing'].median():.1f}%")
    print(f"  Min:     {results_df['pct_increasing'].min():.1f}%")
    print(f"  Max:     {results_df['pct_increasing'].max():.1f}%")
    
    # Count quarters above/below 50%
    above_50 = (results_df['pct_increasing'] >= 50).sum()
    below_50 = (results_df['pct_increasing'] < 50).sum()
    print(f"\nQuarters with majority increasing: {above_50} ({above_50/len(results_df)*100:.1f}%)")
    print(f"Quarters with majority decreasing: {below_50} ({below_50/len(results_df)*100:.1f}%)")
    
    print(f"\nAverage Shareholder Change (2Q):")
    print(f"  Mean:   {results_df['avg_change'].mean():,.0f} shareholders")
    print(f"  Median: {results_df['median_change'].median():,.0f} shareholders")
    
    # Recent trend
    print("\nRecent Quarters (Last 5):")
    print("-"*80)
    for _, row in results_df.tail(5).iterrows():
        direction = "↑" if row['pct_increasing'] >= 50 else "↓"
        print(f"{row['quarter_date'].date()}  |  {row['pct_increasing']:5.1f}%  {direction}  |  "
              f"{row['num_compared']:,} stocks compared")
    
    # Save results
    analyzer.save_results(results_df)
    
    # Plot
    analyzer.plot_results(results_df)
    
    return results_df


if __name__ == "__main__":
    results_df = main()
