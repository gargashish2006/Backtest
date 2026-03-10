#!/usr/bin/env python
"""
Shareholding Concentration Analysis

Calculates the average market cap per shareholder for each stock at quarter-end,
then averages across all stocks to show the trend of ownership concentration over time.

Formula:
- Market Cap per Shareholder = (Stock Price * Outstanding Shares) / Number of Shareholders
- Average across all stocks = Mean of all individual stock values for that quarter
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.scripts import MarketCapCalculator


class ShareholdingConcentrationAnalyzer:
    """Analyzer for shareholding concentration trends"""
    
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
        """
        Convert quarter strings to quarter-end dates
        
        Examples:
        - 'Dec-2016' -> 2016-12-31
        - 'Mar-2017' -> 2017-03-31
        - 'Jun-2017' -> 2017-06-30
        - 'Sep-2017' -> 2017-09-30
        - 'Q3 FY2025' -> 2024-12-31 (Q3 ends Dec)
        """
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
                
                # Q1 FY2025 means Apr-Jun 2024, Q2 = Jul-Sep 2024, Q3 = Oct-Dec 2024, Q4 = Jan-Mar 2025
                quarter_end_months = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}
                month, day = quarter_end_months[quarter_num]
                
                # Adjust year based on quarter
                if quarter_num == 4:  # Q4 ends in March of FY year
                    year = fy_year
                else:  # Q1-Q3 end in previous calendar year
                    year = fy_year - 1
                
                return pd.Timestamp(year=year, month=month, day=day)
            
            else:
                # Try parsing as date directly
                return pd.to_datetime(quarter_str)
                
        except Exception as e:
            print(f"Warning: Could not parse quarter '{quarter_str}': {e}")
            return None
    
    def analyze_concentration_over_time(self):
        """
        Calculate average market cap per shareholder for each quarter (OPTIMIZED)
        
        Returns:
            DataFrame with columns: quarter_date, avg_market_cap_per_shareholder, num_stocks
        """
        print("\nAnalyzing shareholding concentration over time...")
        
        # Parse quarters to dates
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
        
        # OPTIMIZATION: Create a price lookup table for efficient matching
        print("  Building price lookup table...")
        
        # For each ISIN and quarter_date combination, find the nearest price
        # Create a copy of price data with date as datetime
        price_lookup = self.price_df.copy()
        
        # Get all unique quarter dates
        unique_quarters = valid_data['quarter_date'].unique()
        
        # Create a cross-join of ISINs and quarter dates for vectorized lookup
        # This is more efficient than looping
        print("  Matching prices to quarter dates (vectorized)...")
        
        all_results = []
        
        # Process in batches by quarter for memory efficiency
        for i, quarter_date in enumerate(sorted(unique_quarters), 1):
            if i % 5 == 0:
                print(f"    Processing quarter {i}/{len(unique_quarters)}: {quarter_date.date()}")
            
            # Get stocks for this quarter
            quarter_stocks = valid_data[valid_data['quarter_date'] == quarter_date].copy()
            
            # Get prices within +/- 10 days of quarter end
            date_min = quarter_date - pd.Timedelta(days=10)
            date_max = quarter_date + pd.Timedelta(days=10)
            
            relevant_prices = price_lookup[
                (price_lookup['date'] >= date_min) & 
                (price_lookup['date'] <= date_max)
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
            
            # Filter out invalid values
            valid_calcs = merged[merged['market_cap_per_shareholder'] > 0]
            
            if len(valid_calcs) > 0:
                all_results.append({
                    'quarter_date': quarter_date,
                    'avg_market_cap_per_shareholder': valid_calcs['market_cap_per_shareholder'].mean(),
                    'median_market_cap_per_shareholder': valid_calcs['market_cap_per_shareholder'].median(),
                    'num_stocks': len(valid_calcs),
                    'total_stocks_in_quarter': len(quarter_stocks)
                })
        
        results_df = pd.DataFrame(all_results)
        results_df = results_df.sort_values('quarter_date')
        
        print(f"\n✅ Processed {len(results_df)} quarters")
        
        return results_df
    
    def save_results(self, results_df, filename=None):
        """Save results to CSV"""
        if filename is None:
            filename = f"shareholding_concentration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        output_dir = self.base_path / 'analysis' / 'outputs' / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        results_df.to_csv(output_path, index=False)
        
        print(f"\n✅ Results saved to: {output_path}")
        return output_path


def main():
    """Main execution"""
    print("="*70)
    print("SHAREHOLDING CONCENTRATION ANALYSIS")
    print("="*70)
    
    analyzer = ShareholdingConcentrationAnalyzer()
    
    # Analyze concentration over time
    results_df = analyzer.analyze_concentration_over_time()
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nAnalysis Period: {results_df['quarter_date'].min().date()} to {results_df['quarter_date'].max().date()}")
    print(f"Total Quarters: {len(results_df)}")
    print(f"\nAverage Market Cap per Shareholder:")
    print(f"  Overall Mean: ₹{results_df['avg_market_cap_per_shareholder'].mean():,.2f}")
    print(f"  Min: ₹{results_df['avg_market_cap_per_shareholder'].min():,.2f} ({results_df[results_df['avg_market_cap_per_shareholder'] == results_df['avg_market_cap_per_shareholder'].min()]['quarter_date'].values[0]})")
    print(f"  Max: ₹{results_df['avg_market_cap_per_shareholder'].max():,.2f} ({results_df[results_df['avg_market_cap_per_shareholder'] == results_df['avg_market_cap_per_shareholder'].max()]['quarter_date'].values[0]})")
    
    # Show recent trend
    print("\nRecent Values (Last 10 quarters):")
    print("-"*70)
    for _, row in results_df.tail(10).iterrows():
        print(f"{row['quarter_date'].date()}  |  ₹{row['avg_market_cap_per_shareholder']:>12,.2f}  |  {row['num_stocks']} stocks")
    
    print("="*70)
    
    # Save results
    output_path = analyzer.save_results(results_df, 'shareholding_concentration_analysis.csv')
    
    return results_df, output_path


if __name__ == "__main__":
    results_df, output_path = main()
